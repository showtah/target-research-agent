# OpenAI Agents Project

This repository contains AI agents built using the OpenAI Agents SDK, designed to perform specific research and information gathering tasks.

## Project Structure

```
my_project/
├── company_search_agent/       # Company research agent module
│   ├── tools/                  # Custom tools for the agent
│   │   ├── create_query_tool.py
│   │   ├── target_search_tool.py
│   │   └── __init__.py
│   ├── agent.py                # Agent definition
│   ├── run.py                  # Runner script with UI
│   ├── schemas.py              # Output schemas
│   ├── agents_doc.md           # Documentation
│   └── __init__.py
├── run_company_research.py     # Entry point script
└── .env                        # Environment variables (API keys)
```

## Available Agents

### Company Research Agent

A specialized agent that performs deep research on companies based on user queries. The agent:

1. Takes a user query about a company
2. Creates focused search queries 
3. Performs web searches using these queries
4. Generates a comprehensive markdown summary
5. Creates a mindmap visualization of the key information

#### Usage

To use the company research agent:

```bash
python my_project/run_company_research.py
```

Then enter your company research query when prompted.

## Requirements

- Python 3.8+
- OpenAI API key (stored in .env file)
- Tavily API key for web search (stored in .env file)

## Environment Setup

Create a `.env` file in the project root with:

```
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key
```

## Extending the Project

To add new agents or tools:
1. Create a new folder for your agent in the `my_project` directory
2. Define your tools in a separate `tools` directory
3. Create an agent definition file
4. Add a runner script

Each agent should follow the pattern established in the company research agent. 