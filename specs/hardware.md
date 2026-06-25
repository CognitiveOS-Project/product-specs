# Recommended Hardware for CognitiveOS

Version: 1.0.0

## Overview

This document catalogs the hardware platforms suitable for running CognitiveOS, from heavy-lift Wide Model inference nodes to lightweight Raw Model reflex controllers and peripheral MCP bridges.

Links point to official manufacturer stores or primary tier-1 industrial distributors to ensure authenticity and documentation quality for professional deployment.

## Hardware Table

| Device | Role in CognitiveOS | Est. Price (USD) | Link |
|--------|---------------------|------------------|------|
| **NVIDIA Jetson AGX Orin** | High-level Brain (Wide Model) | $1,999+ | [NVIDIA Store](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/) |
| **NVIDIA Jetson Orin NX (16GB)** | Balanced Agent Node | $599+ | [Seeed Studio](https://www.seeedstudio.com/NVIDIA-Jetson-Orin-NX-Module-16GB-p-5582.html) |
| **Raspberry Pi 5 (8GB)** | Edge Reflex / MCP Bridge | $80 - $100 | [Raspberry Pi Store](https://www.raspberrypi.com/products/raspberry-pi-5/) |
| **ESP32-S3 DevKitC-1** | Peripheral / Sensor MCP Node | $8 - $15 | [Espressif Store](https://www.espressif.com/en/products/devkits/esp32-s3-devkitc-1/overview) |
| **Seeed Studio reComputer J4012** | Industrial Deployment Node | $699+ | [Seeed Studio](https://www.seeedstudio.com/reComputer-J4012-p-5573.html) |

## Implementation Notes

### Factory-Direct vs Distributor

While NVIDIA and Raspberry Pi maintain direct storefronts, distributors like Seeed Studio or Digikey are often preferred for development kits because they offer modular carrier boards and pre-integrated thermal solutions that are ready for immediate deployment.

### Software Compatibility

All listed devices support standard Linux-based stacks (Ubuntu/Debian/Alpine) or can be flashed with custom distributions, making them ideal targets for the cognitiveosd daemon and the MCP bridge ecosystem.

### MCP Connectivity

The ESP32-S3 units are excellent for expanding CognitiveOS reach. Since core-mcp-bridges provides the hardware abstraction layer, ESP32-S3 nodes can act as bridges for specialized industrial sensors or legacy serial devices, communicating back to the main CognitiveOS brain via standard protocols (serial MCP, GPIO, or network).

## Deployment Roles

| Role | Recommended Device | Rationale |
|------|-------------------|-----------|
| Primary inference (Wide Model) | Jetson AGX Orin | GPU tensor cores for large GGUF models (7B+) |
| Balanced agent node | Jetson Orin NX (16GB) | Mid-range GPU, fits in smaller enclosures |
| Edge reflex (Raw Model) | Raspberry Pi 5 (8GB) | Sufficient RAM for 0.5B-3B GGUF at Q4 |
| Industrial deployment | reComputer J4012 | Rugged carrier, wide temp range, long lifecycle |
| Peripheral MCP bridge | ESP32-S3 | Low power, built-in WiFi/BLE, sensor integration |

## See Also

- [Architecture](architecture.md) — two-tier brain layer (Raw + Wide Model)
- [Raw Model](raw-model.md) — raw model spec, distro variants by hardware tier
- [core-mcp-bridges](https://github.com/CognitiveOS-Project/core-mcp-bridges) — MCP bridge implementations
- [cognitiveos-distro](https://github.com/CognitiveOS-Project/cognitiveos-distro) — image builder per target
