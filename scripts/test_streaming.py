
import asyncio
import time
import os
import sys

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfsn_controller.llm_async import call_deepseek_streaming, call_gemini_streaming

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def test_streaming(model_name: str, stream_func):
    print(f"\nTesting Streaming for {model_name}...")
    
    prompt = "Count from 1 to 5 slowly."
    start = time.time()
    first_token_time = None
    chunks = 0
    full_text = ""
    
    try:
        async for chunk in stream_func(prompt, temperature=0.7):
            if first_token_time is None:
                first_token_time = time.time()
                latency = (first_token_time - start) * 1000
                print(f"  First token latency: {latency:.2f}ms")
            
            chunks += 1
            full_text += chunk
            # Print a dot for each chunk to visualize streaming
            print(".", end="", flush=True)
            
        print(f"\n  Total chunks: {chunks}")
        print(f"  Total time: {(time.time() - start):.2f}s")
        print(f"  Response length: {len(full_text)} chars")
        
        if chunks > 1:
            print("  ✅ Streaming Verified (received multiple chunks)")
        else:
            print("  ⚠️ Only 1 chunk received (might not be streaming effectively)")
            
    except Exception as e:
        print(f"\n  ❌ Failed: {e}")

async def main():
    # Test DeepSeek if key exists
    if os.environ.get("DEEPSEEK_API_KEY"):
        await test_streaming("DeepSeek", call_deepseek_streaming)
    else:
         print("Skipping DeepSeek (No API Key)")

    # Test Gemini if key exists
    if os.environ.get("GEMINI_API_KEY"):
        await test_streaming("Gemini", call_gemini_streaming)
    else:
        print("Skipping Gemini (No API Key)")

    if not os.environ.get("DEEPSEEK_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
        print("\nNote: Mock Clients do not support streaming yet in this implementation, so this test might fail or skip if no real keys are present.")

if __name__ == "__main__":
    asyncio.run(main())
