# YouTube Learner

A skill that watches YouTube videos, transcribes them, and learns from the content. Demonstrates how a skill with MCP servers and a rich system prompt can give the Wide Model entirely new capabilities.

## cognitive.json

```json
{
  "name": "youtube-learner",
  "version": "0.1.0",
  "description": "Learn from YouTube video transcripts and content",
  "author": "Your Name",
  "license": "MIT",
  "hardware_requirements": {
    "min_ram_mb": 512,
    "min_storage_mb": 200
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "yt-transcriber",
        "command": "./tools/mcp-yt-transcriber",
        "args": ["--cache-dir", "/cognitiveos/data/youtube-cache"]
      }
    ],
    "capabilities": ["youtube.transcribe", "youtube.search", "youtube.analyze"]
  }
}
```

## System Prompt

**`prompts/system.md`**
```
You are a YouTube learning assistant. Your job is to extract knowledge from videos.

When the user gives you a YouTube URL:
1. Call cognitiveos.youtube.transcribe with the URL to get the transcript
2. Analyze the transcript for:
   - Main topic and thesis
   - Key concepts and terminology
   - Code snippets or technical steps (if applicable)
   - Arguments and counter-arguments
   - Sources and references mentioned
3. Summarize the video in a structured format
4. Optionally save the summary to ~/learnings/<topic>.md

When the user asks a question:
1. Search your learning database for relevant content
2. If found, answer with citations to the source video
3. If not found, ask if they want to watch a video on the topic

Always cite source URLs when referencing learned information.
```

## Build & Install

```bash
cpm init youtube-learner --template mcp-bridge
cd youtube-learner

# Build the YouTube transcript MCP server
go build -o tools/mcp-yt-transcriber ./cmd/yt-transcriber

# Install locally
tar czf youtube-learner-0.1.0.cgp .
cpm install ./youtube-learner-0.1.0.cgp
```

## What Happens

1. The daemon spawns `yt-transcriber`, which registers tools like `cognitiveos.youtube.transcribe`
2. The MCP server handles YouTube API calls, transcript extraction (via yt-dlp or YouTube Data API), and caching
3. The Wide Model uses the system prompt to drive the conversation, calling tools as needed
4. The Wide Model can save learnings to disk for later retrieval across sessions

## Usage

```
User: "I want to learn about transformers. Find a good explanation on YouTube"
  → Wide Model calls cognitiveos.youtube.search("transformer neural network explained")
  → Server returns [ { title: "Transformers for Beginners", url: "https://...", views: 245K } ]
  → Wide Model picks the best match and asks: "I found 'Transformers for Beginners' (245K views). Watch it?"
User: "Yes"
  → Wide Model calls cognitiveos.youtube.transcribe("https://youtube.com/watch?v=...")
  → Server returns transcript with timestamps
  → Wide Model analyzes and summarizes:
     "Transformer architecture (Vaswani et al. 2017):
       1. Self-attention mechanism — each word attends to every other word
       2. Multi-head attention — 8 parallel attention heads capture different relationships
       3. Positional encoding — preserves word order information
       Saved to ~/learnings/transformers.md"
  → Wide Model: "Watched and analyzed. Key points saved to your learnings folder."
```

```
User (next session): "What's the difference between transformers and RNNs?"
  → Wide Model searches ~/learnings/
  → Found relevant notes from yesterday's video
  → "Based on the 'Transformers for Beginners' video you watched yesterday:
     RNNs process tokens sequentially (O(n) steps), while transformers
     process all tokens in parallel (O(1) steps) via self-attention.
     This is why transformers are faster to train."
```
