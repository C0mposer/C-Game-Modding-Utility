# ModC Transpiler

Compiler/Transpiler that converts ModC (name work WIP) to standard C code. It should be a superset of C, and all standard C should be unaffected.

## Features

### Symbols
- **Single-build symbols**:
```c
symbol u32 gems @ 0x80123456;
symbol void* object_ptr @ 0x80123456;
symbol u8 gem_values[5] @ 0x80676767;

symbol void KillPlayer(void) @ 0x80654321;
symbol int ReturnCompletionPercent(void) @ 0x80069420;
```
- **Multi-build symbols**: Fully implemented - generates separate symbol files for each build variant
```c
symbol u32 gems @ {
    "NTSC": 0x80123456,
    "PAL":  0x80654321,
    "J":    0x80987654,
};
```
- **Generated files**: 
  - `symbols/build.txt` - Single-build symbol address mappings
  - `symbols/PAL.txt`, `symbols/NTSC.txt`, `symbols/J.txt` - Multi-build symbol files (one per build variant)

### @ Operator
Transforms memory offset access to pointer arithmetic:

**Explicit cast read:**
```c
u32 health = (u32)player@0x00;
```
Becomes:
```c
u32 health = *((u32*)((u8*)player + 0x00));
```

**Inferred read:**
```c
u16 health = player@0x14;
```
Becomes:
```c
u16 health = *((u16*)((u8*)player + 0x14));
```

**Explicit cast write:**
```c
(u32)player@0x00 = 0xDEADBEEF;
//OR
player@0x00 = (u32)0xDEADBEEF;
```
Becomes:
```c
*((u32*)((u8*)player + 0x00)) = 0xDEADBEEF;
```

**Inferred write:**
```c
player@0x04 = 100;
```
Becomes:
```c
*((u32*)((u8*)player + 0x04)) = 100;
```

### Once Blocks
Transforms one-time initialization blocks:
```c
once {
    printf("Initialized!\n");
}
```
Becomes:
```c
static bool _once_flag_1 = false;
if (!_once_flag_1) {
    _once_flag_1 = true;
    printf("Initialized!\n");
}
```

### Struct Methods
Transforms struct methods to C functions with `me` parameter:

**Method definition:**
```c
struct Player {
    u32 health;
    u32 mana;
    
    method void Heal(u32 amount) {
        me->health += amount;
        if (me->health > 100) {
            me->health = 100;
        }
    }
    
    method void Update() {
        me->mana++;
    }
}
```

Becomes:
```c
typedef struct Player__tag {
    u32 health;
    u32 mana;
} Player;

void Player_Heal(Player* me, u32 amount) {
    me->health += amount;
    if (me->health > 100) {
        me->health = 100;
    }
}

void Player_Update(Player* me) {
    me->mana++;
}
```

**Method calls:**
```c
player.Heal(10);
player->Update();
```

Becomes:
```c
Player_Heal(&player, 10);
Player_Update(player);
```

**Note:** Inside methods, use `me->` to access struct members. The `this` keyword is also supported and gets transformed to `me->`.

### Explicit Struct Offsets
Allows specifying exact memory offsets for struct members:

```c
struct Thing {
    u32 a;
    u32 b;
    u32 c @ 0x40;  // Explicit offset
}
```

Becomes:
```c
typedef struct Thing__tag {
    u32 a;
    u32 b;
    u8 _pad_0x08[0x38];  // Padding to reach 0x40
    u32 c;
} Thing;
```

It calculates and inserts padding (`_pad_0xXX`) to ensure members are at the specified offsets. This is useful when working with game memory structures that have not been fully reversed (great idea ebbe)

### Foreach Loops
Transforms ModC foreach loops to C for loops:

**Array iteration:**
```c
foreach player in players {
    player.Update();
}
```
Becomes:
```c
for (int _i_player = 0; _i_player < 4; _i_player++) {
    Player* player = &players[_i_player];
    player.Update();
}
```

**With index:**
```mc
foreach player, idx in players {
    printf("Player %d\n", idx);
}
```

**Range loops:**
```mc
foreach i in 0..10 {
    printf("%d\n", i);
}
```
Becomes:
```c
for (int i = 0; i < 10; i++) {
    printf("%d\n", i);
}
```

**Null-terminated iteration (`[null]`):**
Iterates over a pointer/array until a null element (0x00) is found:
```c
foreach c in world_string[null] {
    printf("%c", c);
}
```
Becomes:
```c
for (char* c = world_string; c != NULL; c++) {
    printf("%c", c);
}
```

**Runtime size iteration (`[size=expr]`):**
Iterates with a size determined at runtime:
```c
s32 count = GetPlayerCount(); //Runtime size
foreach player in players[size=count] {
    player->Update();
}
```
Becomes:
```c
s32 count = GetPlayerCount();
for (int _i_player = 0; _i_player < count; _i_player++) {
    Player* player = &players[_i_player];
    player->Update();
}
```

The `size` expression can be a variable, function call, or any expression:
```c
foreach score in scores[size=GetMaxScores() + 1] {
    ProcessScore(score);
}
```

### Replace Functions
Completely replaces a function implementation:
```mc
replace void ReturnCompletionPercentage(void) @ 0x80012345 {
    return 100;  // Always return 100%
}
```
Generates:
- **C function**: `void ReturnCompletionPercentage(void) { return 100; }`
- **ASM file** (PS1/MIPS): `j ReturnCompletionPercentage` + `nop` (branch delay)
- **ASM file** (PS2): `j ReturnCompletionPercentage` (no branch delay)
- **ASM file** (PowerPC/GameCube/Wii): `b ReturnCompletionPercentage`

### Stub Functions
Disables a function by making it return immediately:

**With return type:**
```c
stub void AnnoyingCutscene @ 0x80012345;
stub u32 GetAnnoyingValue @ 0x80012348;
stub SomeFunction @ 0x80123456; // Without return type or args
```

Generates:
- **ASM file** (PS1/MIPS): `jr $ra` + `nop` (return immediately, branch delay)
- **ASM file** (PS2): `jr $ra` (return immediately, no branch delay)
- **ASM file** (PowerPC/GameCube/Wii): `blr` (return immediately)

### Hooks
Generate hook asm files

**Simple hook (no arguments, void return):**
```c
hook j GameLoop @ 0x80030000 {
    printf("Game loop called!\n");
}
```
Becomes:
```c
void Hook_GameLoop(void) {
    printf("Game loop called!\n");
}

// Hook_GameLoop.s
j Hook_GameLoop # MIPS
```

Generates:
- **C function**: With the specified return type and parameters
- **ASM file** (PS1/MIPS): `j/jal Hook_Name` + `nop` (branch delay)
- **ASM file** (PS2): `j/jal Hook_Name` (no branch delay)
- **ASM file** (PowerPC/GameCube/Wii): `b/bl Hook_Name`

### "in" Operator
Provides convenient set membership and range checks:

**Range checks:**
```mc
if (player.health in 0..20) {
    PlayWarning();
}
```
Becomes:
```c
if ((player.health >= 0 && player.health <= 20)) {
    PlayWarning();
}
```

**Set checks:**
```mc
if (enemy.type in [GRUNT, SOLDIER, BOSS]) {
    enemy.Attack();
}
```
Becomes:
```c
if ((enemy.type == GRUNT || enemy.type == SOLDIER || enemy.type == BOSS)) {
    enemy.Attack();
}
```

Works with simple variables, complex expressions, and @ operator results

### len() Function
Get the compile-time size of arrays. Works with symbol arrays, regular C arrays, struct member arrays, and nested arrays:

**Symbol arrays:**
```c
symbol Player players[4] @ 0x80200040;
s32 count = len(players);  // Returns 4
```

**Regular C arrays:**
```c
char buffer[256];
int values[10] = {};
s32 buf_size = len(buffer);   // Returns 256
s32 val_count = len(values);  // Returns 10
```

**Struct member arrays:**
```c
struct Entity {
    char name[32];
    int scores[8];
};

Entity entity;
s32 name_len = len(entity.name);    // Returns 32
s32 scores_len = len(entity.scores); // Returns 8
```

**Multi-dimensional arrays:**
```c
symbol u32 matrix[5][10] @ 0x80200400;
s32 rows = len(matrix);      // Returns 5 (first dimension)
s32 cols = len(matrix[0]);   // Returns 10 (second dimension)
```

**In expressions:**
```c
s32 total = len(players) + len(scores);
if (len(players) > 0) {
    ProcessPlayers(players, len(players));
}
```

**With foreach:**
```c
foreach player in players[size=len(players)] {
    player->Update();
}
```

The `len()` function extracts array sizes from:
- Global and local `symbol` array declarations
- Global and local regular C array declarations (including `static`, `const`, `extern`)
- Struct member arrays (uses `sizeof` pattern as fallback)
- Multi-dimensional arrays (extracts dimensions from type information)

### Include Mechanism
Include other ModC files to organize symbols and share code.

#### `.mch` Files (Header Files)
For files intended to be included in multiple `.mc` files, use the `.mch` extension. These generate `.h` files with include guards automatically:

```c
// include/symbols.mch
// ModC header file - symbols that can be included in multiple files

symbol u32 player_health @ 0x80000000;
symbol Player* current_player @ 0x80000004;
symbol Enemy enemies[10] @ 0x80001000;
```

```mc
// main.mc
#include <symbols.mch>

void UpdatePlayer() {
    if (player_health > 0) {
        current_player->Update();
    }
}
```

**Generated files:**
- `include/symbols.h` (with include guards):
```c
#ifndef MODC_SYMBOLS_H
#define MODC_SYMBOLS_H

typedef struct Enemy__tag Enemy;
typedef struct Player__tag Player;

extern Player* current_player;
extern Enemy enemies[10];
extern u32 player_health;

#endif // MODC_SYMBOLS_H
```

- `main.c`:
```c
#include <stdio.h>
#include <math.h>
#include "types.h"

#include "symbols.h"

void UpdatePlayer() {
    if (player_health > 0) {
        Update(current_player);
    }
}
```

**Best Practices:**
- Use `.mc` files for symbols used in a single file
- Use `.mch` files for symbols shared across multiple files (placed in `include/` directory often)
- `.mch` files automatically get include guards, so they're safe to include multiple times

## Platform Configuration

The transpiler supports multiple platforms with flexible configuration:

### Supported Platforms

**MIPS Platforms:**
- `mips` - Generic MIPS (with branch delays)
- `ps1` - PlayStation 1 (with branch delays)
- `ps2` - PlayStation 2 (no branch delays)

**PowerPC Platforms:**
- `powerpc` or `ppc` - Generic PowerPC (no branch delays)
- `gamecube` - Nintendo GameCube (no branch delays)
- `wii` - Nintendo Wii (no branch delays)

**Branch Delays:**
- PS1 and generic MIPS require `nop` after branch instructions (`j`, `jal`, `jr`)
- PS2 has no branch delays, so no `nop` is inserted
- PowerPC platforms never have branch delays

### Command-Line
```bash
python transpiler.py input.mc --platform ps1
python transpiler.py input.mc --platform ps2
python transpiler.py input.mc --platform gamecube
python transpiler.py input.mc --platform wii
```

## Usage

```bash
python transpiler.py input.mc [output_dir] [--platform mips|powerpc]
```

This will:
1. Transpile `input.mc` → `input.c`
2. Generate `symbols/build.txt` with single-build symbol addresses
3. Generate `symbols/PAL_v1.txt`, `symbols/NTSC_v1.txt`, etc. for multi-build symbols
4. Generate extern declarations for symbols
5. Generate `asm/*.s` files for hooks, replace, and stub functions

## Example

**Input (test_basic.mc):**
```mc
symbol u32 value @ 0x80100000;
symbol Player players[4] @ 0x80200040;

void TestFunction() {
    once {
        printf("Initialized!\n");
    }
    
    foreach player in players {
        u32 health = (u32)player@0x00;
        player@0x04 = 100;
    }
}
```

**Output (test_basic.c):**
```c
void TestFunction() {
    static bool _once_flag_1 = false;
    if (!_once_flag_1) {
        _once_flag_1 = true;
        printf("Initialized!\n");
    }
    
    for (int _i_player = 0; _i_player < 4; _i_player++) {
        Player* player = &players[_i_player];
        u32 health = *((u32*)((u8*)(player) + 0x00));
        *((u32*)((u8*)(player) + 0x04)) = 100;
    }
}
```

