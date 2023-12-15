#include <custom_types.h>
#include <symbols.h>
#include <common.h>
#include <buttons.h>
#include <hashcodes.h>

long color_white = 0x80808080;
int* textGUI;
EXRect mapInfoRect = {12, 100, 160, 30};

void drawGUIText(int* element, char* wText, char* pText, EXRect* rect, long col) {
    EXRect dropshadow = {
        rect->x+2,
        rect->y+2,
        rect->w,
        rect->h
    };

    long shadowColor = 0x00000080;

    GUI_Item_DrawText(textGUI, gpPanelWnd, wText, pText, &dropshadow, &shadowColor);
    GUI_Item_DrawText(textGUI, gpPanelWnd, wText, pText, rect, col);
}

void printMap(int* mapPtr) {
    

    //XWnd_SetText(gpPanelWnd, HT_File_Panel, HT_Font_Test, &color_white, 1, 2);
    //XWnd_TextPrint(gpPanelWnd, c);
}

void MainHook(void)
{
    if (textGUI == 0) {
        textGUI = CreateGUI_Item();
        *(textGUI + 0x57) = 0; //Set text alignment (top-left)

        InGamePrintf("Created GUI Item at address %x\n", textGUI);
    }

    if (IsButtonsJustPressed(z_button)) {
        //InGamePrintf("text = %x\n", textGUI);
        int i;
        for (i = 0; i<NUM_MAPS; i++) {
            int* map = gMapList[i];
            InGamePrintf("map %d: %x\n", i+1, map);
        }
    }

    char* c = GetText(&gGameText, HT_Text_Realm1, 0, 0);
    drawGUIText(textGUI, c, 0, &mapInfoRect, &color_white);

    //if (gpPlayerItem != 0) {
    //    drawPlayerPos();
    //}
    
    //XWnd_SetText(gpPanelWnd, HT_File_Panel, HT_Font_Test, &color_white, 1, 2);
    //XWnd_TextPrint(gpPanelWnd, c);
}