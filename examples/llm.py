from lightning_sdk.llm import LLM

# public models
llm = LLM(name="openai/gpt-4o")
print(llm.chat("Hello, how are you?"))
# Hello! I'm just a computer program, so I don't have feelings, but I'm here and ready to help you. How can I assist you today?

# user models
llm = LLM(name="my-models/llama4-scout")
print(llm.chat("Hello, how are you?"))
# Hello! I'm just a language model, I don't have feelings like humans do, but I'm functioning properly and ready to help you with any questions or tasks you have! How can I assist you today?
