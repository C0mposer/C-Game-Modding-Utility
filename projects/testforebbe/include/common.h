#ifndef COMMON_H
#define COMMON_H
#include <custom_types.h>

#define NUM_MAPS 40

enum Buttons
{
    dpad_up = 0b1,
    dpad_down = 0b10,
    dpad_left = 0b100,
    dpad_right = 0b1000,

    lanalog_up = 0b10000,
    lanalog_down = 0b100000,
    lanalog_left = 0b1000000,
    lanalog_right = 0b10000000,

    ranalog_up = 0b100000000,
    ranalog_down = 0b1000000000,
    ranalog_left = 0b10000000000,
    ranalog_right = 0b100000000000,

    b_button = 0b1000000000000,
    a_button = 0b10000000000000,
    x_button = 0b100000000000000,
    y_button = 0b1000000000000000,

    l3_unused = 0b10000000000000000,
    r3_unused = 0b100000000000000000,
    start = 0b1000000000000000000,
    select = 0b10000000000000000000,

    l_button = 0b100000000000000000000,
    l2_unused = 0b1000000000000000000000,
    r_button = 0b10000000000000000000000,
    z_button = 0b100000000000000000000000
};
typedef enum Buttons Buttons;

struct ButtonsBitfield
{
    byte dpad_up:1;
    byte dpad_down:1;
    byte dpad_left:1;
    byte dpad_right:1;

    byte lanalog_up:1;
    byte lanalog_down:1;
    byte lanalog_left:1;
    byte lanalog_right:1;

    byte ranalog_up:1;
    byte ranalog_down:1;
    byte ranalog_left:1;
    byte ranalog_right:1;

    byte b_button:1;
    byte a_button:1;
    byte x_button:1;
    byte y_button:1;

    byte l3_unused:1;
    byte r3_unused:1;
    byte start:1;
    byte select_button:1;

    byte l_button:1;
    byte l2_unused:1;
    byte r_button:1;
    byte z:1;
};
typedef struct ButtonsBitfield ButtonsBitfield;

struct EXVector
{
    float X;
    float Y;
    float Z;
    float W;
};
typedef struct EXVector EXVector;

struct EXRect
{
    int x;
    int y;
    int w;
    int h;
};
typedef struct EXRect EXRect;

long getGenericStructLong(int* s, int offs) {
    return *((long*) ((char*) s + offs));
}
float getGenericStructFloat(int* s, int offs) {
    return *((float*) ((char*) s + offs));
}
int getGenericStructInt(int* s, int offs) {
    return *((int*) ((char*) s + offs));
}

#endif /* COMMON_H */
