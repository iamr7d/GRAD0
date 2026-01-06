# GRAD0: AI News Director System

GRAD0 is an automated AI system designed to produce TV-style news content. It aggregates real-time news from RSS feeds, uses Large Language Models (LLMs) to curate and script stories, and automatically matches them with relevant stock video footage.

## Core Features

- **Automated News Aggregation**: robust fetching of news from multiple RSS sources.
- **Intelligent Curation**: Uses OpenAI/LangChain to cluster, filter, and select top trending stories.
- **Visual Director**: Generates specific visual search terms to find relevant stock footage (via Pexels or similar) to match the story context.
- **Show Queue Management**: Manages a "run of show" playlist (`QueueManager`) for sequential playback.
- **Ticker Generation**: Automatically generates scrolling news ticker text.

## Tech Stack

- **Python**
- **LangChain** (Orchestration)
- **OpenAI GPT-4/3.5** (Content Generation)
- **Feedparser** (RSS)
- **Requests** (API connectivity)

## Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/iamr7d/GRAD0.git
   cd GRAD0
   ```

2. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   _Core dependencies include: `langchain`, `langchain-openai`, `feedparser`, `requests`, `json_repair`._

3. **Configuration**
   - Configure `OPENAI_API_KEY` in your environment or `config.py`.
   - Ensure necessary API keys for video search are set.

## Modules

- `tools/video_finder.py`: Main logic for video search and queue management.
- `BreakingNode`: Analyzes urgency of incoming wire stories.
- `CollectorNode`: Aggregates and summarizes trending topics.
