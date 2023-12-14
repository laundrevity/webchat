<script>
	import { onMount, tick } from "svelte";
	import { Marked } from "marked";

	import { markedHighlight } from "marked-highlight";
  	import hljs from "highlight.js";
	import { writable } from 'svelte/store';

	// Configure marked with marked-highlight and highlight.js
	const marked = new Marked(
		markedHighlight({
			langPrefix: "hljs language-",
			highlight: function(code, lang) {
				const language = hljs.getLanguage(lang) ? lang : "plaintext";
				return hljs.highlight(code, { language }).value;
			},
		})
	);

	const botLastActivity = writable(Date.now());

	let currentTime = "Connecting...";
	let message = "";
	let conversation = [];
	let isBotResponding = false;
	let chatContainerWidth = '800px'; // Default width
	let chatContainer;

	let timeSocket;
	let messageSocket;
	let stopSocket;

	onMount(() => {
		timeSocket = new WebSocket("ws://localhost:8765/time");
		messageSocket = new WebSocket("ws://localhost:8765/message");
		stopSocket = new WebSocket("ws://localhost:8765/stop");
		chatContainer = document.querySelector('.chat-container');


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
                    let lastSegment = lastMessage.segments[lastMessage.segments.length - 1];
                    if (lastSegment.type === data.type) {
                        // Append to the existing segment if the type is the same
                        lastSegment.text += data.message;
                        lastSegment.renderedText = marked.parse(lastSegment.text);
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
            segments: [{
                text: data.message,
                type: data.type,
                renderedText: marked.parse(data.message),
            }],
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
				segments: [{
					text: message,
					renderedText: marked.parse(message),
				}],
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
		const shouldScroll = chatContainer.scrollTop + chatContainer.clientHeight + 75 >= chatContainer.scrollHeight;

		if (shouldScroll) {
			console.log('Auto-scrolling...', {
				element: chatContainer,
				scrollHeight: chatContainer.scrollHeight,
				clientHeight: chatContainer.clientHeight,
				scrollTop: chatContainer.scrollTop
			});

			const scrollOptions = {
				top: chatContainer.scrollHeight,
				behavior: 'smooth'
			};

			// Try scrolling to the bottom using an alternative approach if needed
			if ('scrollTo' in chatContainer) {
				chatContainer.scrollTo(scrollOptions);
			} else if ('scrollTop' in chatContainer) {
				// Fallback for browsers that do not support `scrollTo` with options
				chatContainer.scrollTop = chatContainer.scrollHeight;
			} else {
				console.error('Unable to auto-scroll: chatContainer does not have scrollTo or scrollTop.');
			}
		}
	}

</script>

<div class="app-container">
	<div class="clock">Current Time: {currentTime}</div>

	<div class="containers-wrapper">
		<div class="chat-container" on:resize={handleChatContainerResize} bind:this={chatContainer}>
			{#each conversation as msg}
				<div class="message {msg.author}">
					<strong>{msg.author}:</strong>
					<span class="message-content">
						{#each msg.segments as segment}
							<span class={`segment ${segment.type}`}>{@html segment.renderedText}</span>
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

	:root {
    	--chat-container-width: 800px; /* Default width */
	}

	:global(body) {
		background-color: #121212;
		color: white;
		margin: 0;
		font-family: Arial, sans-serif; /* Optional: Set a default font */
	}

	:global(.message .hljs) {
  		background-color: inherit; /* Inherit the background color from the message container */
  		color: inherit; /* Inherit the text color from the message container */
	}


	.app-container {
		display: grid;
		place-items: center;
		gap: 10px;
		margin: auto;
		padding: 20px;
		background-color: #121212;
	}

	.containers-wrapper {
		display: flex;
		flex-direction: column;
		align-items: center; /* Center align the containers */
		/* max-width: 800px; Maximum width */
	}

	.chat-container,
	.input-container {
		width: 100%;
		min-width: 800px; /* Set a minimum width */
	}

	.chat-container {
		width: var(--chat-container-width);
		height: 600px;
		min-height: 600px;
		border: 1px solid #333;
		background-color: #1a1a1a;
		padding: 10px;
		/* overflow-y: auto; */
		overflow: auto;
		resize: both;
		box-sizing: border-box;
		margin-bottom: 10px;
		/* display: flex;
		flex-direction: column-reverse; */
		display: flex;
		flex-direction: column;
	}

	.input-container {
		display: flex;
		flex-direction: column;
		resize: vertical;
		overflow: hidden;
	}

	.input-container textarea {
		flex-grow: 1;
		padding: 10px;
		background-color: #262626;
		color: white;
		border: 1px solid #333;
		resize: none;
	}

	.button-container {
		display: flex;
		justify-content: start;
	}

	.input-container button {
		padding: 5px 10px;
		margin-right: 10px;
		background-color: #333; /* Dark background for buttons */
		color: white;
		border: none;
		cursor: pointer;
	}

	.message {
		border: 1px solid #444;
		padding: 5px;
		margin: 5px 0;
		white-space: pre-wrap;
		width: 100%;
		overflow-wrap: break-word;
	}

	.User {
		background-color: #170016;
	}

	.Bot {
		background-color: #001300;
	}

	.message-content, .segment {
 	   display: inline;
	   white-space: pre-wrap;
	}

    .segment.tool_call {
        color: yellow;
    }

    .segment.tool_call_result {
        color: orange;
    }

    .segment.text_response {
        color: white;
    }

</style>
