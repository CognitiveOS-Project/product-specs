# EdTech Company: Khan Academy Tutor-in-a-Box

**Company profile:** Educational content company that wants to package structured knowledge (curated Q&A, embedded concepts, progress tracking) into a self-contained AI tutor.

This tutorial shows a hybrid package — a `gguf-model` for the embedding engine combined with an MCP bridge for the quiz server. The result: an offline-capable tutoring system that tracks the learner's progress across sessions.

## Why .cgp Instead of a Web App

| Concern | Web-based learning platform | .cgp Tutor |
|---------|---------------------------|------------|
| Offline access | Requires internet connection | Fully offline after install |
| Privacy | User data stored on company servers | All data local — no telemetry |
| Latency | Network round-trip for every question | Local inference, sub-100ms responses |
| Personalization | Profile on server | Cross-session progress stored locally |
| Cost | Server infrastructure for each user | Zero marginal cost per user |
| Integration | Separate login, notifications | Works alongside other skills, same AI |

## cognitive.json

```json
{
  "name": "khan-academy-tutor",
  "version": "3.1.0",
  "description": "Khan Academy Tutor — math, science, history with adaptive learning",
  "author": "Khan Academy",
  "license": "CC-BY-NC-SA",
  "download_url": "https://registry.cognitive-os.org/v1/patches/khan-academy-tutor/3.1.0/download",
  "checksum": {
    "sha256": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"
  },
  "source": {
    "repository": "https://github.com/khanacademy/tutor-cgp",
    "issues": "https://github.com/khanacademy/tutor-cgp/issues"
  },
  "hardware_requirements": {
    "min_ram_mb": 4096,
    "min_storage_mb": 2048
  },
  "brain": {
    "wide_model": {
      "base_model": "all-MiniLM-L6-v2",
      "weights": {
        "remote": {
          "source": "huggingface",
          "model_id": "sentence-transformers/all-MiniLM-L6-v2",
          "filename": "all-MiniLM-L6-v2-Q4_K_M.gguf",
          "format": "gguf",
          "quant": "Q4_K_M",
          "size_bytes": 23900000
        }
      }
    }
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "quiz-engine",
        "command": "./tools/mcp-quiz",
        "args": ["--deck-root", "/cognitiveos/data/khan-academy-tutor/decks"]
      }
    ],
    "capabilities": [
      "tutor.quiz.generate",
      "tutor.quiz.grade",
      "tutor.concept.search",
      "tutor.progress.report",
      "tutor.flashcard.review"
    ]
  }
}
```

## System Prompt

**`prompts/system.md`:**
```
You are a Khan Academy Tutor. You help students learn through adaptive questioning and spaced repetition.

Teaching workflow:
1. When a student asks a topic, search your concept database with cognitiveos.tutor.concept.search
2. Assess their current level with a few diagnostic questions
3. Present concepts in the recommended learning order
4. After each lesson, generate a quiz with cognitiveos.tutor.quiz.generate
5. Grade responses with cognitiveos.tutor.quiz.grade
6. Track correct/incorrect with cognitiveos.tutor.progress.report

Pedagogical rules:
- Never give the answer directly — guide the student to discover it
- If they get 3 questions wrong in a row, suggest a prerequisite topic
- Review past mistakes at the start of each session
- Use the Feynman technique: "Explain it to me like I'm 10"
- Celebrate progress: "You've mastered 15/20 algebra concepts — great job!"
```

## Built-In Curriculum Decks

The package ships with curated curriculum data as embedded JSON files in the archive:

```
tools/
├── mcp-quiz                    # Quiz engine binary
└── decks/
    ├── algebra-1.json          # 200 Q/A pairs, concept map, prerequisites
    ├── geometry-basics.json    # 150 Q/A pairs
    ├── world-history-101.json  # 180 Q/A pairs
    └── physics-mechanics.json  # 160 Q/A pairs
```

Each deck includes:
- Question/answer pairs with difficulty level
- Concept dependency graph (master "variables" before "linear equations")
- Common misconceptions and how to correct them
- External references (Khan Academy video IDs for optional online cross-reference)

## Build & Install

```bash
cpm init khan-academy-tutor --template gguf-model
cd khan-academy-tutor

# Build the quiz engine
go build -o tools/mcp-quiz ./cmd/quiz

# Package curriculum decks
cp -r decks/ tools/decks/

# Package
tar czf khan-academy-tutor-3.1.0.cgp .
cpm publish ./khan-academy-tutor-3.1.0.cgp
```

```bash
# Install — downloads embedding model + curriculum data
cpm install khan-academy-tutor
```

## What Happens

1. **Weight download** — 24 MB embedding model from Hugging Face
2. **Hardware audit** — 4 GB RAM, 2 GB storage
3. **Quiz engine spawns** — `mcp-quiz` loads the curriculum decks into memory
4. **Concept index** — embedding model indexes all Q/A pairs for semantic search
5. **Progress tracking** — `/cognitiveos/data/khan-academy-tutor/progress.json` created
6. **Spaced repetition schedule** — engine computes optimal review intervals

## Usage

```
Student: "I want to learn algebra"
  → Wide Model calls cognitiveos.tutor.concept.search("algebra prerequisites")
  → Quiz engine: "Prerequisites: basic arithmetic, fractions. Ready to start?"
Student: "Yes"
  → Wide Model: "Let's start with the basics. What is 3x + 5 = 20? Solve for x."
Student: "x = 5"
  → Wide Model calls cognitiveos.tutor.quiz.grade("3x + 5 = 20", "x = 5")
  → Quiz engine: correct (100%), confidence: high
  → "Correct! Let's try a harder one."

Student: "x = 4"
  → Quiz engine: incorrect — common mistake (subtraction order)
  → Wide Model: "Almost! Remember to subtract before dividing.
     3x + 5 = 20 → subtract 5: 3x = 15 → divide by 3: x = 5.
     Let's try another: 2x + 10 = 30"
```

### Cross-Session Progress

```
Student (next day): "Review algebra"
  → Wide Model calls cognitiveos.tutor.progress.report()
  → Quiz engine: "algebra-1: 65% mastered, 3 concepts weak (linear equations, factoring)"
  → "Welcome back! You're 65% through algebra. Let's review the 3 concepts you struggled with yesterday.

     Yesterday you made errors on:
     1. 2(x + 3) = 12 → you wrote x = 6 (correct: x = 3)
     2. 5x - 3 = 2x + 9 → you wrote x = 12 (correct: x = 4)

     Let's try similar problems to build confidence."
```

## Offline-Only Mode

In schools with no internet, the tutor runs fully offline after initial install:

```bash
# IT admin installs on 30 devices from a USB drive
cpm install khan-academy-tutor-3.1.0.cgp --offline

# All 30 devices now have the full tutor — no internet needed
# Progress syncs via local network when available:
#   cognitiveos.data.sync /cognitiveos/data/khan-academy-tutor/
# Teacher dashboard receives anonymized progress reports
```

## Marketplace: Selling Curriculum Decks

Other publishers can create supplemental decks:

```bash
cpm install khan-academy-tutor           # Base tutor
cpm install publisher-advanced-calculus  # Paid add-on deck
  # Adds calculus concepts to the tutor's knowledge base
  # Requires unlock code for commercial use
```
