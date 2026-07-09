# Study Buddy

A flashcard and quiz generator backed by a locally-downloaded embedding model. Demonstrates a `gguf-model` template package — a model with remote weights that are downloaded at install time.

## cognitive.json

```json
{
  "name": "study-buddy",
  "version": "1.0.0",
  "description": "Flashcard and quiz generator using local embeddings",
  "author": "Your Name",
  "license": "MIT",
  "download_url": "https://registry.cognitive-os.org/v1/patches/study-buddy/1.0.0/download",
  "checksum": {
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "hardware_requirements": {
    "min_ram_mb": 2048,
    "min_storage_mb": 500
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
        "name": "embedding-server",
        "command": "./tools/mcp-embed",
        "args": ["--model", "/cognitiveos/patches/study-buddy/weights/all-MiniLM-L6-v2-Q4_K_M.gguf"]
      }
    ],
    "capabilities": ["study.flashcard", "study.quiz", "study.embed"]
  }
}
```

## System Prompt

**`prompts/system.md`**
```
You are a study assistant that creates flashcards and quizzes from study material.

Workflow:
1. User provides text (notes, article, transcript, PDF summary)
2. Generate flashcards (front/back pairs) from key concepts
3. Generate a quiz and track the user's answers
4. Use the embedding model to find similar concepts across sessions

Flashcard format:
  Q: "What is attention?" | A: "A mechanism that weighs the importance of different input parts"

Always save flashcards to /cognitiveos/data/study-buddy/decks/<subject>.json
Load existing decks at the start of each session for spaced repetition.
```

## Build & Install

```bash
cpm init study-buddy --template gguf-model
cd study-buddy

# Build the embedding MCP server
go build -o tools/mcp-embed ./cmd/embed

# Package and install
tar czf study-buddy-1.0.0.cgp .
cpm install ./study-buddy-1.0.0.cgp
```

## What Happens

This is the most complex install flow, showcasing multiple integration points:

1. **Schema validation** — `brain.wide_model.weights.remote` is parsed, validated, and stored
2. **Hardware audit** — 2 GB RAM, 500 MB storage — if the system doesn't have it, cpm rejects the install
3. **Weight download** — cpm downloads the 24 MB GGUF embedding model from Hugging Face (`source: "huggingface"`, `model_id: "sentence-transformers/all-MiniLM-L6-v2"`)
4. **Integrity check** — SHA-256 of downloaded file is compared against `checksum.sha256`
5. **Extraction** — archive contents go to `/cognitiveos/patches/study-buddy/`, model weights go to `/cognitiveos/patches/study-buddy/weights/`
6. **Daemon loads the embedding model** — `wide_model_load` message sent to inference engine
7. **MCP server spawns** — `embedding-server` loads the model and registers tools
8. **Wide Model prompt chain** — the study buddy system prompt is injected

## Usage

```
User: "I'm studying transformer architectures. Here are my notes: [pastes notes]"
  → Wide Model generates flashcards:
     Q: "What problem does self-attention solve?"
     A: "It captures relationships between all positions in a sequence, solving the long-range dependency problem of RNNs"
     Q: "How many heads does multi-head attention typically use?"
     A: "8 or 16 parallel attention heads"
     Q: "What is positional encoding?"
     A: "A technique to inject position information since self-attention has no inherent notion of order"
  → Saves to /cognitiveos/data/study-buddy/decks/transformer-architectures.json
  → "I created 12 flashcards from your notes. Would you like to take a quiz?"

User: "Yes, quiz me"
  → Wide Model presents flashcards in random order, tracks correct/incorrect
  → Uses spaced repetition — cards you get wrong appear more frequently
  → "You got 8/12 correct. Let's review the 4 you missed."
```

```
User (next day): "Review transformers"
  → Wide Model loads saved deck
  → Prioritizes cards you got wrong yesterday
  → "Welcome back! Let's start with the 4 cards you missed yesterday."
```

## Cross-Session Memory

The embedding model enables semantic search across study sessions:

```
User: "What was that thing about RNNs vs transformers?"
  → Wide Model calls cognitiveos.study.embed("RNN vs transformer comparison")
  → Embedding server computes vector and searches all saved decks by cosine similarity
  → Returns matching flashcards from yesterday's session
  → "I found it from yesterday's notes:
     'RNNs process tokens sequentially. Transformers process all tokens in parallel.'"
```
