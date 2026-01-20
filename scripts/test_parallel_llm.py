
import asyncio
import time
import os
import sys

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfsn_controller.llm_async import generate_patches_parallel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def main():
    print("Testing parallel LLM generation...")
    
    # Check for API keys
    dk = os.environ.get("DEEPSEEK_API_KEY")
    gk = os.environ.get("GEMINI_API_KEY")
    
    if not dk and not gk:
        print("No API keys found. This test will likely use Mock Clients (which is fine for logic check).")
    
    prompt = "Fix a typo in README.md"
    temps = [0.1, 0.5, 0.9]
    model = "deepseek-chat"
    
    start = time.time()
    patches = await generate_patches_parallel(
        prompt=prompt,
        temperatures=temps,
        model=model
    )
    end = time.time()
    
    duration = end - start
    print(f"Generated {len(patches)} patches in {duration:.2f}s")
    
    for i, p in enumerate(patches):
        print(f"Patch {i}: {p.get('mode', 'unknown')}")
        if "error" in p:
            print(f"  Error: {p['error']}")

    if len(patches) == len(temps):
        print("\n✅ Verification Successful: Received expected number of patches.")
    else:
        print("\n❌ Verification Failed: Count mismatch.")

if __name__ == "__main__":
    asyncio.run(main())
