from bot.models import Message, StreamChunk, ToolCall

from pydantic import ValidationError
from blacksheep import WebSocket
from typing import List, Dict
import asyncio
import httpx
import json
import os

class StreamingInterruptedException(Exception):
    def ___init__(self, message):
        super().__init__(message)


class InterruptFlag:
    def __init__(self):
        self.streaming_interrupted = asyncio.Event()

    def set_streaming_interrupt(self):
        self.streaming_interrupted.set()

    def clear_streaming_interrupt(self):
        self.streaming_interrupted.clear()

    async def wait_for_interrupt(self):
        await self.streaming_interrupted.wait()


class OpenAIService:
    def __init__(self, tools_json: List[Dict]):
        self.tools_json = tools_json
        self.flag = InterruptFlag()
        self.timeout = 300
        self.verbose = False

        self.client = httpx.AsyncClient()
        bearer_token = f"Bearer {os.getenv('OPENAI_API_KEY')}"
        self.headers = {
            "Authorization": bearer_token,
            "Content-Type": "application/json",
        }
        self.url = "https://api.openai.com/v1/chat/completions"

    async def get_message(self, messages: List[Message], ws: WebSocket, tools: bool = False):
        payload = {
            "messages": [
                message.model_dump(exclude_unset=True) for message in messages
            ],
            "model": "gpt-4-1106-preview",
            "stream": True
        }
        if tools:
            payload["tools"] = self.tools_json
        
        try:
            stream_chunks = await self.get_stream_chunks(payload, ws)
            message = self.parse_stream_chunks(stream_chunks, ws)
        except StreamingInterruptedException as e:
            print(e)
            message = Message(role="assistant", content=str(e))

        if (
            message.role == "assistant"
            and not message.content
            and not message.tool_calls
        ):
            error_content = "I'm sorry, there was an error processing the response -- both `content` and `tool_calls` are empty."
            print(error_content)
            return Message(
                role="assistant",
                content=error_content,
            )
        return message

    async def get_stream_chunks(self, payload: Dict, ws: WebSocket) -> List[StreamChunk]:
        print("Assistant: ", end="")
        chunks = []
        bad_status_code = False
        partial_content = ""
        partial_tool_calls = []

        async with self.client.stream(
            "POST", self.url, json=payload, headers=self.headers, timeout=300
        ) as response:
            if response.status_code != 200:
                bad_status_code = True
                await response.aread()

            if not bad_status_code:
                self.flag.clear_streaming_interrupt()

                async for line in response.aiter_lines():
                    # print(line, flush=True)

                    trim_line = line[6:]

                    if trim_line and not self.flag.streaming_interrupted.is_set():
                        try:
                            line_json = json.loads(trim_line)

                            try:
                                stream_chunk = StreamChunk.model_validate(line_json)

                                content = stream_chunk.choices[0].delta.content
                                if content:
                                    partial_content += content
                                    print(content, end="")
                                    await ws.send_json({"message": content, "type": "text_response"})

                                tool_calls = stream_chunk.choices[0].delta.tool_calls
                                if tool_calls:
                                    tool_call_function = tool_calls[0].function
                                    if tool_call_function.name:
                                        partial_tool_calls.append(
                                            {
                                                "function_name": tool_call_function.name,
                                                "args": "",
                                            }
                                        )
                                        print(f"{tool_call_function}: ", end="")
                                        await ws.send_json({"message": f"{tool_call_function}:", "type": "tool_call"})
                                    
                                    if tool_call_function.arguments:
                                        print(tool_call_function.arguments, end="")
                                        partial_tool_calls[-1][
                                            "args"
                                        ] += tool_call_function.arguments
                                        await ws.send_json({"message": tool_call_function.arguments, "type": "tool_call"})

                                chunks.append(stream_chunk)
                                if self.verbose:
                                    print(stream_chunk)

                            except ValidationError as e:
                                if self.verbose:
                                    print(f"ValidationError parsing {line_json}: {e}")

                            # print(json.dumps(line_json, indent=4), flush=True)

                        except json.JSONDecodeError:
                            if trim_line == "[DONE]":
                                if self.verbose:
                                    print(f"Finished consuming stream.")
                            else:
                                if self.verbose:
                                    print(f"Got JSON decode error on line: {trim_line}")

                    if self.flag.streaming_interrupted.is_set():
                        raise StreamingInterruptedException(
                            f"Streaming interrupted: received CTRL+C from user. Partial content: {partial_content if partial_content else partial_tool_calls}"
                        )

        if bad_status_code:
            print(
                f"Got bad status code: {response.status_code}, {response.content=}\npayload: {json.dumps(payload, indent=4)}"
            )

        print("")

        return chunks
    
    def parse_stream_chunks(self, chunks: List[StreamChunk], ws: WebSocket) -> Message:
        # Initialize empty Message object
        message = Message(role="assistant")

        # Initialize empty content string and tool_calls list
        content = ""
        tool_calls: List[ToolCall] = []

        # We will track whether we are inside a tool call or not
        inside_tool_call = False

        if chunks:
            first_choice = chunks[0].choices[0]
            if first_choice.delta.role == "assistant" and first_choice.delta.tool_calls:
                tool_calls.append(first_choice.delta.tool_calls[0])
                inside_tool_call = True

        for chunk in chunks:
            # Assume that we only care about the first choice in each chunk
            choice = chunk.choices[0]
            delta = choice.delta

            if (
                delta.role == "assistant"
                and delta.content is None
                and delta.tool_calls is None
            ):
                # The beginning of either text response or tool call sequence
                continue
            elif delta.role is None and delta.content is not None:
                # Accumulate the text response content
                content += delta.content
            elif delta.role is None and delta.tool_calls:
                # Handle the tool call sequence
                for tool_call in delta.tool_calls:
                    # If we encounter a new full ToolCall object, we are starting a new tool call
                    if tool_call.id:
                        tool_calls.append(tool_call)
                        inside_tool_call = True

                    elif inside_tool_call:
                        # We are in the middle of processing a tool call, so we accumulate argument data
                        # NOTE: This assumes that `arguments` are being sent in the correct sequence
                        last_tool_call = tool_calls[-1]
                        if last_tool_call.function.arguments is None:
                            last_tool_call.function.arguments = ""
                        last_tool_call.function.arguments += (
                            tool_call.function.arguments
                        )

            elif choice.finish_reason == "stop":
                # End of a text response sequence
                break
            elif choice.finish_reason == "tool_calls":
                # End of a tool call sequence
                break

        if content:
            message.content = content
        else:
            message.tool_calls = tool_calls

        return message