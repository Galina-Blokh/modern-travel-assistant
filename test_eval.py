import asyncio
from agent import create_agent
from langchain_core.messages import HumanMessage

async def evaluate_agent():
    print("Testing Agent Connection and Tools...\n")
    agent = create_agent(use_fallback=False)
    
    test_queries = [
        "What is the weather in Paris?",
        "Tell me about the country of Japan.",
        "What are the top attractions in Rome?"
    ]

    for query in test_queries:
        print(f"User: {query}")
        messages = [HumanMessage(content=query)]
        
        try:
            print("Assistant: ", end="", flush=True)
            async for event in agent.astream_events({"messages": messages}, version="v2"):
                kind = event["event"]
                
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        print(content, end="", flush=True)
                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    print(f"\n[Running tool: {tool_name}...]\n", end="", flush=True)
            
            print("\n" + "-" * 50 + "\n")
        except Exception as e:
            print(f"\nError evaluating query '{query}': {str(e)}\n")
            print("-" * 50 + "\n")

if __name__ == "__main__":
    asyncio.run(evaluate_agent())
