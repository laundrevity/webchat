<script>
	import { onMount, tick } from "svelte";
	import { Marked } from "marked";

	import { markedHighlight } from "marked-highlight";
	import hljs from "highlight.js";
	import { writable } from "svelte/store";

	// Configure marked with marked-highlight and highlight.js
	const marked = new Marked(
		markedHighlight({
			langPrefix: "hljs language-",
			highlight: function (code, lang) {
				const language = hljs.getLanguage(lang) ? lang : "plaintext";
				return hljs.highlight(code, { language }).value;
			},
		}),
	);

	const botLastActivity = writable(Date.now());

	let currentTime = "Connecting...";
	let message = "";
	let conversation = [];
	let isBotResponding = false;
	let chatContainerWidth = "800px"; // Default width
	let chatContainer;

	let timeSocket;
	let messageSocket;
	let stopSocket;

	onMount(() => {
		timeSocket = new WebSocket("ws://localhost:8765/time");
		messageSocket = new WebSocket("ws://localhost:8765/message");
		stopSocket = new WebSocket("ws://localhost:8765/stop");
		chatContainer = document.querySelector(".chat-container");

		timeSocket.onmessage = (event) => {
			currentTime = event.data;
		};

		messageSocket.onmessage = async (event) => {
			botLastActivity.set(Date.now()); // Update the store value
			// console.log("messageSocket.onmessage: ", event);
			const data = JSON.parse(event.data);

			if (conversation.length > 0 && isBotResponding) {
				let lastMessage = conversation[conversation.length - 1];
				if (lastMessage.author === "Bot") {
					let lastSegment =
						lastMessage.segments[lastMessage.segments.length - 1];
					if (lastSegment.type === data.type) {
						// Append to the existing segment if the type is the same
						lastSegment.text += data.message;
						lastSegment.renderedText = marked.parse(
							lastSegment.text,
						);
					} else {
						// Add a new segment for a different type
						lastMessage.segments.push({
							text: data.message,
							type: data.type,
							renderedText: marked.parse(data.message),
						});
					}
				} else {
					// New bot message
					startNewBotMessage(data);
				}
			} else {
				// First message from the bot or after user's message
				startNewBotMessage(data);
			}

			conversation = [...conversation];
			// 	lastMessage.text += data.message;
			// 	lastMessage.renderedText = marked.parse(lastMessage.text);
			// } else {
			// 	conversation.push({
			// 		author: "Bot",
			// 		text: data.message,
			// 		type: data.type,
			// 		renderedText: marked.parse(data.message),
			// 	});
			// 	isBotResponding = true;
			// }
			// conversation = [...conversation]; // Update to trigger reactivity
			// // await tick();
			// autoScroll();
		};
	});

	function startNewBotMessage(data) {
		conversation.push({
			author: "Bot",
			segments: [
				{
					text: data.message,
					type: data.type,
					renderedText: marked.parse(data.message),
				},
			],
		});
		isBotResponding = true;
	}

	$: {
		$botLastActivity; // Reactive dependency on the bot's last activity
		tick().then(autoScroll); // This makes sure the DOM has updated before scrolling
		console.log("react");
	}

	function sendMessage() {
		if (messageSocket && messageSocket.readyState === WebSocket.OPEN) {
			let userMessage = {
				author: "User",
				segments: [
					{
						text: message,
						renderedText: marked.parse(message),
					},
				],
			};
			conversation.push(userMessage);
			isBotResponding = false;
			conversation = [...conversation]; // Update to trigger reactivity
			messageSocket.send(message);
			message = "";
		}
	}

	function handleKeydown(event) {
		// Check if the Enter key is pressed
		if (event.key === "Enter" && !event.shiftKey) {
			event.preventDefault(); // Prevents the default action of the Enter key
			sendMessage();
		}
	}

	function stopResponse() {
		if (stopSocket && stopSocket.readyState === WebSocket.OPEN) {
			stopSocket.send("@#STOP#@");
		}
	}

	function handleChatContainerResize(event) {
		chatContainerWidth = `${event.target.offsetWidth}px`;
	}

	function autoScroll() {
		// const shouldScroll = chatContainer.scrollHeight - chatContainer.clientHeight <= chatContainer.scrollTop + 1;
		// let shouldScroll = true;
		const shouldScroll =
			chatContainer.scrollTop + chatContainer.clientHeight + 75 >=
			chatContainer.scrollHeight;

		if (shouldScroll) {
			console.log("Auto-scrolling...", {
				element: chatContainer,
				scrollHeight: chatContainer.scrollHeight,
				clientHeight: chatContainer.clientHeight,
				scrollTop: chatContainer.scrollTop,
			});

			const scrollOptions = {
				top: chatContainer.scrollHeight,
				behavior: "smooth",
			};

			// Try scrolling to the bottom using an alternative approach if needed
			if ("scrollTo" in chatContainer) {
				chatContainer.scrollTo(scrollOptions);
			} else if ("scrollTop" in chatContainer) {
				// Fallback for browsers that do not support `scrollTo` with options
				chatContainer.scrollTop = chatContainer.scrollHeight;
			} else {
				console.error(
					"Unable to auto-scroll: chatContainer does not have scrollTo or scrollTop.",
				);
			}
		}
	}
</script>

<div class="app-container">
	<div class="clock">Current Time: {currentTime}</div>

	<div class="containers-wrapper">
		<div
			class="chat-container"
			on:resize={handleChatContainerResize}
			bind:this={chatContainer}
		>
			{#each conversation as msg}
				<div class="message {msg.author}">
					<strong>{msg.author}:</strong>
					<span class="message-content">
						{#each msg.segments as segment}
							<span class={`segment ${segment.type}`}
								>{@html segment.renderedText}</span
							>
						{/each}
					</span>
				</div>
			{/each}
		</div>

		<div class="input-container">
			<textarea
				bind:value={message}
				placeholder="Type a message..."
				rows="2"
				on:keydown={handleKeydown}
			></textarea>
			<div class="button-container">
				<button on:click={sendMessage}>Send</button>
				<button on:click={stopResponse}>Stop</button>
			</div>
		</div>
	</div>
</div>

<style>
	@import url("https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&display=swap");

	:root {
		--background-dark: #121212;
		--background-lighter: #1e1e1e;
		--bot-message-bg: #003300;
		--user-message-bg: #330033;
		--text-color: #ffffff;
		--input-bg-color: #262626;
		--border-color: #333333;
		--button-bg-color: #444444;
		--scrollbar-bg: #2e2e2e;
		--scrollbar-thumb-bg: #555555;
		--border-radius: 10px;
		--chat-container-width: 800px;
	}

	:global(body) {
		background-color: var(--background-dark);
		color: var(--text-color);
		margin: 0;
		font-family: "Roboto", sans-serif;
	}

	.app-container {
		display: grid;
		place-items: center;
		gap: 10px;
		padding: 20px;
		/* width: 100%; */
		/* max-width: var(--chat-container-width)1; */
		margin: auto;
	}

	.containers-wrapper {
		display: flex;
		flex-direction: column;
		align-items: center;
		/* width: 100%; */
	}

	.chat-container,
	.input-container {
		width: 100%;
		min-width: 800px; /* Set a minimum width */
	}

	.chat-container {
		width: var(--chat-container-width);
		background-color: var(--background-lighter);
		border: 1px solid var(--border-color);
		box-sizing: border-box;
		padding: 10px;
		margin-bottom: 10px;
		overflow: auto;
		resize: both;
		height: 600px;
		min-height: 600px;
		border-radius: var(--border-radius);
		display: flex;
		flex-direction: column;
	}

	.input-container {
		display: flex;
		flex-direction: column;
		background: var(--input-bg-color);
		border: 1px solid var(--border-color);
		border-radius: var(--border-radius);
		margin-top: 10px;
		resize: vertical;
		overflow: hidden;
	}

	.input-container textarea {
		background: var(--input-bg-color);
		color: var(--text-color);
		padding: 10px;
		border: 1px solid #333;
		resize: none;
		flex-grow: 1;
	}

	.button-container {
		display: flex;
		justify-content: flex-start;
		padding: 10px;
	}

	.button-container button {
		background-color: var(--button-bg-color);
		color: var(--text-color);
		border: none;
		margin-right: 10px;
		padding: 8px 16px;
		border-radius: var(--border-radius);
		cursor: pointer;
		transition: background-color 0.3s;
	}

	.button-container button:hover {
		background-color: lighten(var(--button-bg-color), 10%);
	}

	.message {
		background-color: var(--background-lighter);
		border: 1px solid var(--border-color);
		border-radius: var(--border-radius);
		margin: 5px 0;
		padding: 10px;
		white-space: pre-wrap;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
	}

	.User {
		background-color: var(--user-message-bg);
	}

	.Bot {
		background-color: var(--bot-message-bg);
	}

	.segment {
		display: inline;
	}

	.segment.tool_call {
		color: yellow;
	}

	.segment.tool_call_result {
		color: orange;
	}

	.segment.text_response {
		color: var(--text-color);
	}
</style>
