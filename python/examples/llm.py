from lightning_sdk.llm import LLM

# public models
llm = LLM(name="openai/gpt-4o")
print(llm.chat("Hello, how are you?", conversation="test"))
# Hello! I'm just a computer program, so I don't have feelings, but I'm here and ready to help you. How can I assist you today?

# lightning-ai provided models
llm = LLM(name="lightning-ai/Llama-4-Scout-17B-16E-Instruct")
print(llm.chat("Hello, how are you?"))
# Hello! I'm just a computer program, so I don't have feelings, but I'm here and ready to help you. How can I assist you today?

# user models
llm = LLM(name="llama4-scout", teamspace="kaeun/default-teamspace")
print(llm.chat("Hello, how are you?"))
# Hello! I'm just a language model, I don't have feelings like humans do, but I'm functioning properly and ready to help you with any questions or tasks you have! How can I assist you today?

# continue conversation using conversation param
llm = LLM(name="openai/gpt-4o")
llm.chat("Hello, how are you?", conversation="basic")
llm.chat("Hello world!", conversation="basic")

# print conversation history
print(llm.get_history("basic"))
# reset conversation
llm.reset_conversation("basic")

# list existing conversations
llm = LLM(name="openai/gpt-4o")
llm.chat("Hello, how are you?", conversation="conv1")
llm.chat("Hello world!", conversation="conv2")
print(llm.list_conversations())
# ['conv1', 'conv2', 'test']

# streaming
for chunk in llm.chat("Hi!", conversation="basic", stream=True):
    print(chunk, end="", flush=True)
