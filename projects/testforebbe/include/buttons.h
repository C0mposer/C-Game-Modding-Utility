#ifndef BUTTONS_H
#define BUTTONS_H

#include <custom_types.h>
#include <symbols.h>
#include <common.h>

bool IsButtonsJustPressed(Buttons button)
{
    static Buttons was_button_just_pressed = 0;

    //If button was pressed, and has not been pressed yet, set the bit for that button
    if ((current_buttons & button) && !(was_button_just_pressed & button))
    {
        was_button_just_pressed |= (current_buttons & button);
        return true;
    }

    //If button was released, clear the bit for that button
    else if (!(current_buttons & button) && (was_button_just_pressed & button))
    {
        was_button_just_pressed &= ~button;
    }


    return false;
}

bool IsButtonsHeldDown(Buttons button)
{
    if ((current_buttons & button))
    {
        return true;
    }
    else
    {
        return false;
    }
}

short IsButtonsHeldDown2(Buttons button)
{
    if ((current_buttons & 5))
    {
        return 1;
    }
    else
    {
        return 2;
    }
}

int IsButtonsHeldDown3(Buttons button)
{
    if ((current_buttons & 3))
    {
        return 2;
    }
    else
    {
        return false;
    }
}

#endif /* BUTTONS_H */
