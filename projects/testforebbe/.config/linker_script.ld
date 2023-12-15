INPUT(../../../.config/symbols/symbols.txt)
INPUT(../../../.config/symbols/function_symbols.txt)
INPUT(../../../.config/symbols/auto_symbols.txt)

MEMORY
{
    /* RAM locations where we'll inject the code for our replacement functions */
    MainCodecave : ORIGIN = 0x803D8FB0, LENGTH = 0x2010
    AutoHook : ORIGIN = 0x80222244, LENGTH = 0x100000
}

SECTIONS
{
    /* Custom section for compiled code */
    /* Custom section for our hook code */
    .AutoHook : 
    {
        main_hook.o(.text)
        main_hook.o(.rodata)
        main_hook.o(.rodata*)
        main_hook.o(.data)
        main_hook.o(.bss)
    } > AutoHook

    .MainCodecave : 
    {
        main.o(.text)
        main.o(.rodata)
        main.o(.rodata*)
        main.o(.data)
        main.o(.bss)
        main.o(.sdata)
        main.o(.sbss)
        main.o(.scommon)
        main.o(.main.o.*)
        *(.text)
        *(.branch_lt)
    } > MainCodecave

    /DISCARD/ :
    {
        *(.comment)
        *(.pdr)
        *(.mdebug)
        *(.reginfo)
        *(.MIPS.abiflags)
        *(.eh_frame)
        *(.gnu.attributes)
    }
}