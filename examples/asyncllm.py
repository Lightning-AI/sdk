import time
from lightning_sdk.llm import LLM

import asyncio
import time
from lightning_sdk.llm import AsyncLLM

def benchmark_sync():
    llm = LLM(name="openai/gpt-4o")
    start = time.time()

    for i in range(10):
        response = llm.chat("Hello, how are you?", conversation=f"sync-test-{i}")
        print(f"Response {i+1}: {response}")

    end = time.time()
    print(f"Total time (sync): {end - start:.2f} seconds")


async def send_request(async_llm, i):
    response = await async_llm.chat("Hello, how are you?", conversation=f"async-test-{i}")
    print(f"Response {i+1}: {response}")

async def benchmark_async():
    async_llm = AsyncLLM(name="openai/gpt-4o")
    start = time.time()

    # Send all 10 requests concurrently
    await asyncio.gather(*(send_request(async_llm, i) for i in range(10)))

    end = time.time()
    print(f"Total time (async): {end - start:.2f} seconds")

if __name__ == "__main__":
    benchmark_sync()
    asyncio.run(benchmark_async())
