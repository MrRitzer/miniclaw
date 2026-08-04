# MiniClaw

A lightweight, modular claw machine controller for hobbyists and developers.

## Overview

MiniClaw is a slim alternative to OpenClaw, designed for embedded systems, home claw machines, and projects where simplicity and low resource usage matter. It provides the core primitives for controlling claw mechanics—up/down, left/right, grab/release—without the overhead of a full featured suite.

## Design Goals

- **Minimal footprint** — Runs on AVR, ESP32, and other microcontrollers with tight memory constraints
- **Simple API** — Control the claw with a handful of clear commands
- **Portable** — No hard dependencies; works with or without an OS
- **Extensible** — Drop-in modules for common claw mechanisms and sensors

## Quick Start

```c
claw_init();
claw_move(X_AXIS, 50);   // move left/right (0-100)
claw_move(Y_AXIS, 75);   // move forward/back (0-100)
claw_grab();             // close claw
claw_release();          // open claw
```

## Architecture

```
claw-core/       — Motor control, positioning, state machine
claw-sensors/    — Current sensing, position反馈
claw-input/      — Joystick, button, serial interfaces
claw-display/    — LED strips, 7-seg, LCD status
```

## Use Cases

- DIY claw machine builds
- Arcade cabinet conversions
- Educational robotics projects
- Drop-in replacement for OpenClaw in resource-constrained environments

## License

MIT
