from bot.openai_service import OpenAIService
from bot.toolkit import ToolKit
from bot.models import Message

from blacksheep import WebSocket
from typing import List
import datetime
import asyncio
import json
import os


class Conversation:
    def __init__(self):
        self.toolkit = ToolKit()
        self.conversation_id = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        self.state = False
        self.messages: List[Message] = []
        
        self.initialize_messages()
        self.openai_service = OpenAIService(self.toolkit.get_tools_json())
    
    def initialize_messages(self):
        system_prompt = open('system.txt').read()

        if self.state:
            print("including system state")
            system_prompt += f"Current project source code:\n{open('state.txt').read()}"

        self.add_message(Message(role="system", content=system_prompt))

    def get_messages_json(self):
        jsons = []
        for message in self.messages:
            jsons.append(message.model_dump(exclude_unset=True, exclude_none=True))
        return jsons

    def add_message(self, message: Message):
        conversations_dir = os.path.join(os.getcwd(), "conversations")
        if not os.path.exists(conversations_dir):
            os.makedirs(conversations_dir)
        self.messages.append(message)

        conversation_path = os.path.join(
            conversations_dir, f"{self.conversation_id}.json"
        )
        with open(conversation_path, "w") as fp:
            json.dump(self.get_messages_json(), fp, indent=4)

    async def add_user_prompt(self, prompt: str, ws: WebSocket):
        self.add_message(Message(role="user", content=prompt))

        # Get a message from GPt
        message = await self.openai_service.get_message(self.messages, ws, tools=True)
        self.add_message(message)

        if message.tool_calls:
            tool_call_tasks = []
            for tool_call in message.tool_calls:
                tool_call_tasks.append(
                    asyncio.create_task(self.toolkit.execute_tool(tool_call))
                )
            results = await asyncio.gather(*tool_call_tasks)
        
            print("=> ")
            await ws.send_json({"message": "\n=>\n", "type": "tool_call"})

            for result in results:
                try:
                    result_json = json.loads(result.replace("\n", ""))
                    print(json.dumps(result_json, indent=4))
                    await ws.send_json({"message": json.dumps(result_json, indent=4) + "\n\n", "type": "tool_call_result"})
                except json.JSONDecodeError as e:
                    error_str = f"Error decoding JSON from {result}: {e}"
                    print(error_str)
                    await ws.send_json({"message": error_str, "type": "tool_call_result"})

            for result, tool_call in zip(results, message.tool_calls):
                self.add_message(
                    Message(
                        role="tool",
                        content=result,
                        tool_call_id=tool_call.id,
                        name=tool_call.function.name,
                    )
                )

            message = await self.openai_service.get_message(
                self.messages, ws, tools=False
            )
            self.add_message(message)
