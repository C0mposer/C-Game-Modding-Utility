# C/C++ Game Modding Utility
![Logo](logo.gif)

**This utility aims to make writing mods for 5th/6th generation console games in C/C++ easier.**   

## Features  
- Supports PS1, PS2, GameCube, & Wii
- GUI and CLI interfaces
- Rebuild's game ISO's
- Live emulator injection into [supported emulators](https://github.com/C0mposer/C-Game-Modding-Utility?tab=readme-ov-file#supported-emulators)
- Multi-version symbol management
- Code cave finder and pattern-based hook detection
- And much more!

[Click here to see the Wiki](https://github.com/C0mposer/C-Game-Modding-Utility/wiki)

## Quick Start:

### Creating a Project
1. Click "Create New Project", and give it a name
2. Choose your games platform
3. Click "Extract ISO File", and choose your games .iso/.bin/.ciso/etc

### 2. Setup code caves & hooks
**Need help finding code caves and hooks?** The tool includes:
- **Codecave Finder** - Scans for free memory space & debug strings
- **Auto-Hook Detection** - Automatically finds every-frame functions

### 3. Write Your First Mod
The tool auto-generated a project with everything you need. Edit `src/main.c`:

```c
// src/main.c
void ModMain(void) {
    // Your mod code here
    player_health = 100;  // Invincibility
}
```

**Working with game symbols:** Define addresses in `symbols/default.txt`, declare types in `include/symbols.h`, then use them like normal variables. [Full symbol guide](https://github.com/C0mposer/C-Game-Modding-Utility/wiki/Using-C-to-Interact-With-In-Game-Symbols)

### 3. Test Your Mod
Click **Compile** in the build tab to compile your mod. Then, you can either inject into your emulator to test, or build an ISO!


## Recommended Tools
 - [Ghidra](https://github.com/NationalSecurityAgency/ghidra/releases) is a swiss army knife for reverse engineering. In combination with the plugins below, it can make decompiling games a much nicer experience:
 ~ [PS1 Ghidra Plugin](https://github.com/lab313ru/ghidra_psx_ldr)
 ~ [PS2 Ghidra Plugin](https://github.com/chaoticgd/ghidra-emotionengine-reloaded)
 ~ [Gamecube/Wii Ghidra Plugin](https://github.com/Cuyler36/Ghidra-GameCube-Loader)
 ~ [N64 Ghidra Plugin](https://github.com/zeroKilo/N64LoaderWV)
 - [Bizhawk](https://tasvideos.org/BizHawk/ReleaseHistory#Bizhawk261) for memory searching in PS1 games
 - [Cheat Engine](https://github.com/cheat-engine/cheat-engine) for memory searching in PS2 games, and other programs
 - [Dolphin Memory Engine](https://github.com/aldelaro5/Dolphin-memory-engine) for memory searching in Gamecube/Wii games
 - [P64 Dev](https://www.pj64-emu.com/nightly-builds) for memory searching in Nintendo 64 games
- [VSCode](https://github.com/microsoft/vscode) or [Sublime](https://www.sublimetext.com/) text editors, for automatic integration with projects
## Supported Emulators
#### Gamecube/Wii Emulators
 - [Dolphin](https://dolphin-emu.org/download)  
 #### PS2 Emulators
 - [PCSX2](https://pcsx2.net/)  
 #### PS1 Emulators
 - [Duckstation](https://github.com/stenzek/duckstation/releases/tag/latest)  
 - [Mednefan 1.31](https://mednafen.github.io/releases/)  
 - [Mednefan 1.29](https://mednafen.github.io/releases/)  
 - [Bizhawk 2.6.1](https://tasvideos.org/BizHawk/ReleaseHistory#Bizhawk261)  

## Bundled Tools
 - [devkitPro](https://github.com/devkitPro) for GCC toolchains targeted towards the Gamecube/Wii PowerPC CPU, as well as utilities for analyzing .dol files
 - [ps2toolchain](https://github.com/ps2dev/ps2toolchain) for GCC toolchains targeted towards the PS2 Emotion Engine CPU.
 - [mkpsxiso](https://github.com/Lameguy64/mkpsxiso) for extracting & rebuilding PS1 disk images.
  - [Ps2IsoTools](https://github.com/Finzenku/Ps2IsoTools) for rebuilding PS2 disk images.
 - [gc_fst](https://github.com/AlexanderHarrison/gc_fst) for extracting & rebuilding Gamecube images.
 - [wiimms-iso-tools](https://github.com/Wiimm/wiimms-iso-tools) for extracting & rebuilding Wii disk images.
 - [DolphinTool](https://github.com/dolphin-emu/dolphin) for converting between the different GC/Wii image formats.
 - [dolphin-memory-engine](https://github.com/aldelaro5/dolphin-memory-engine) for interacting with Dolphin's emulator memory.
 - [pine](https://github.com/GovanifY/pine) for interacting with PCSX2's emulator memory.
  - [xdelta](https://github.com/jmacd/xdelta) for the creation of xdelta patch files
  - [7zip](https://github.com/mcmilk/7-Zip) for solving life's greatest mysteries
  - [Real N64 CRC Tool](https://www.smwcentral.net/?p=section&a=details&id=8799) for updating N64 rom CRC's

## Special Thanks
- Ebbe - For testing the tool, reporting bugs, and suggesting features throughout it's development
- Wafflewizard1 - For creating the icon

## Contact

If you need any help using this utility, feel free to join the community discord: [Join Discord](https://discord.gg/Hw8pSMcB)
