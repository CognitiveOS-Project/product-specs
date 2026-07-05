# Photo Viewer

A skill that displays images on the system framebuffer. Demonstrates a basic MCP bridge skill with a single server binary.

## cognitive.json

```json
{
  "name": "photo-viewer",
  "version": "1.0.0",
  "description": "Display and browse images on the framebuffer",
  "author": "Your Name",
  "license": "MIT",
  "hardware_requirements": {
    "min_ram_mb": 256,
    "min_storage_mb": 50
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "display-mcp",
        "command": "./tools/mcp-display",
        "args": ["--framebuffer", "/dev/fb0"]
      }
    ],
    "capabilities": ["display.render_image", "display.list_images"]
  }
}
```

## System Prompt

**`prompts/system.md`**
```
You are a photo viewer assistant. You can:

1. List images in a directory with `cognitiveos.display.list_images`
2. Display an image fullscreen with `cognitiveos.display.render_image`
3. Zoom, pan, and rotate images

When the user says "show me my photos", list images first,
then ask which one they want to see.
```

## Build & Install

```bash
cpm init photo-viewer --template mcp-bridge
cd photo-viewer

# Write your MCP server (e.g. Go + fbdev)
go build -o tools/mcp-display ./cmd/mcp-display

# Package and install
tar czf photo-viewer-1.0.0.cgp .
cpm install ./photo-viewer-1.0.0.cgp
```

## What Happens

1. `cpm` extracts the archive to `/cognitiveos/patches/photo-viewer/`
2. The daemon spawns `display-mcp` with the declared args
3. `display-mcp` opens a Unix socket and sends an `mcp_register` message listing its tools
4. The daemon responds with `mcp_registered` and indexes the tools
5. The Wide Model can now call `cognitiveos.display.render_image` and `cognitiveos.display.list_images`

## Usage

```
User: "Show me my photos from last weekend"
  → Wide Model calls cognitiveos.display.list_images("~/photos/2026-06/")
  → MCP server returns [ "beach.jpg", "sunset.jpg", "group.jpg" ]
  → Wide Model: "I found 3 photos. Which one would you like to see?"
User: "Show me beach.jpg"
  → Wide Model calls cognitiveos.display.render_image("~/photos/2026-06/beach.jpg")
  → MCP server decodes and renders to /dev/fb0
  → Image appears on screen
```
