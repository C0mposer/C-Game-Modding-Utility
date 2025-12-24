from open_pipe import *
from functions.verbose_print import verbose_print

def GetDolphinBaseAddressAsHexString():
    base_address, stderr = OpenPipeWithStdStreams("prereq/DolphinMemoryEngine/PrintDolphinBaseAddress.exe")
    print("Dolphin MEM1 Address: " + base_address)
    
    base_address_int = int(base_address, base=16)
    if base_address_int == 0x0:
        print("Can't find dolphin MEM1 address.")
    
    return base_address

def GetDolphinBaseAddressAsInt():
    base_address, stderr = OpenPipeWithStdStreams("prereq/DolphinMemoryEngine/PrintDolphinBaseAddress.exe")
    verbose_print("Dolphin MEM1 Address: " + base_address)
    
    base_address_int = int(base_address, base=16)
    if base_address_int == 0x0:
        print("Can't find dolphin MEM1 address.")

    return base_address_int
