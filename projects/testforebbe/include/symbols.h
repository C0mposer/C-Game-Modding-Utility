#ifndef SYMBOLS_H
#define SYMBOLS_H
#include <custom_types.h>
#include <common.h>
#include <hashcodes.h>

in_game Buttons current_buttons; //0x8066AAD0
in_game int* gpPlayer; //0x804CB35C
in_game int* gpPlayerItem; //0x804CB360

in_game int InGamePrintf(char* format, ...); //0x803592a8
in_game int InGameSPrintf(char* str, char* format, ...); //0x80259af8
in_game bool Player_ForceModeChange(int* itemhandler, int animModeHash); // 0x8005b63c
in_game bool gCreatePickup(uint, EXVector); //0x800e1b6c
in_game bool gCreateLightGem(EXVector* position, int SPECI, int PICKUP, float thing, int thing2); //0x8015500c

in_game int* gGameLoop_m_pPanel; //0x8046F374
in_game int* gpGameWnd; //0x804cb3cc
in_game int* gpPanelWnd; //0x804cb3d0
in_game int* gpPanelXWnd; //0x804cb3d4
in_game void GUI_GameText_Print(int* self, uint textHash, float time); //0x80222d58
in_game void BaseWnd_DebugPrint(int* self, char* pText); //0x80302710
in_game void XWnd_TextPrint(int* self, char* pText); //0x8012f72c
in_game void XWnd_SetText(int* self, long File, long Font, long* Col, float Scale, int Align); //0x8012f8dc

in_game int* CreateGUI_Item(void); //0x801a5e14
in_game void GUI_Item_DrawText(int* self, int* XWnd, u16* thing, char* pText, EXRect* rect, long Color); //0x801a9ee8

in_game void GoToMap(int* gameLoop, long GeoCode, long StartPointCode, long MapCode); //0x8023e644
in_game int* GetSpyroMap(long FindFlag); //0x80232df0
in_game int* gMapList[40]; //0x8046ee54

in_game int* gGameText; //0x80455c1c
in_game char* GetText(int* gameText, long textHash, long pWho, int Color); //0x8012df2c

#endif //SYMBOLS_H
