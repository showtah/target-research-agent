#!/usr/bin/env python3
"""
Entry point script for running the company research agent.
This allows the agent to be easily run from the project root.
"""

import asyncio
from company_search_agent.run import main

if __name__ == "__main__":
    asyncio.run(main()) 