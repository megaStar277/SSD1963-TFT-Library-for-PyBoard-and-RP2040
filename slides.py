#
# Slide show
#
import os
import gc
import tft
import pyb
from struct import unpack
from font14 import font14
#
# Global COnstants
#
COUNTER = 5 ## Stop, if no PIR activity for # pictures
TOTAL_COUNTER = 100 ## Stop after # pictures
BANNER_COUNTER = 20 ## every # picture, the banner is shown
BANNER_NAME = "banner.bmp"
TOOLOWBAT = 200 ## Bat Way too low. Must run fromi USB
SCALING = 7.86 ## Voltage divider (680k + 100k)/100k
OFFSET = 0.0  ## Voltag at input diode (if any)
LOWBAT = int((5.4 - OFFSET) / 3.3 / SCALING * 4096) ## 
WARNBAT = int((5.8 - OFFSET) / 3.3 / SCALING * 4096) ##
BANNER_TIME = 5000 ## Time, the banner is shown (ms)
PICT_TIME = 10000 ## Time, a picture is shown (ms)

TFT_SIZE = 9

def displayfile(mytft, name, width, height):
    try:
        with open(name, "rb") as f:
            gc.collect()
            row = 0
            parts = name.split(".") # get extension
            if len(parts) > 1:
                mode = parts[-1].lower()
            if mode == "raw": # raw 16 bit 565 format with swapped bytes
                b = bytearray(width * 2)
                imgheight = os.stat(name)[6] // (width * 2)
                skip = (height - imgheight) // 2
                if skip > 0:
                    mytft.fillRectangle(0, 0, width - 1, skip, (0, 0, 0))
                else:
                    skip = 0
                for row in range(skip, height):
                    n = f.readinto(b)
                    if not n:
                        break
                    tft.TFT_io.swapbytes(b, width * 2)
                    mytft.drawBitmap(0, row, width, 1, b, 16)
                mytft.fillRectangle(0, row, width - 1, height - 1, (0, 0, 0))
            elif mode == "bmp":  # Windows bmp file
                BM, filesize, res0, offset = unpack("<hiii", f.read(14))
                (hdrsize, imgwidth, imgheight, planes, colors, compress, imgsize,
                 h_res, v_res, ct_size, cti_size) = unpack("<iiihhiiiiii", f.read(40))
                if imgwidth <= width: ##
                    skip = ((height - imgheight) // 2)
                    if skip > 0:
                        mytft.fillRectangle(0, height - skip, width - 1, height - 1, (0, 0, 0))
                    else:
                        skip = 0
                    if colors in (1,2,4,8):  # must have a color table
                        if ct_size == 0: # if 0, size is 2**colors
                            ct_size = 1 << colors
                        colortable = bytearray(ct_size * 4)
                        f.seek(hdrsize + 14) # go to colortable
                        n = split_read(f, colortable, ct_size * 4) # read colortable
                        if colors == 1:
                            bsize = imgwidth // 8
                        elif colors == 2:
                            bsize = imgwidth // 4
                        elif colors == 4:
                            bsize = imgwidth // 2
                        elif colors == 8:
                            bsize = imgwidth
                        bsize = (bsize + 3) & 0xfffc # must read a multiple of 4 bytes
                        b = bytearray(bsize)
                        f.seek(offset)
                        for row in range(height - skip - 1, -1, -1):
                            n = f.readinto(b)
                            if n != bsize:
                                break
                            mytft.drawBitmap(0, row, imgwidth, 1, b, colors, colortable)
                    else:
                        f.seek(offset)
                        if colors == 16:
                            bsize = (imgwidth*2 + 3) & 0xfffc # must read a multiple of 4 bytes
                            b = bytearray(bsize)
                            for row in range(height - skip - 1, -1, -1):
                                n = f.readinto(b)
                                if n != bsize:
                                    break
                                mytft.drawBitmap(0, row, imgwidth, 1, b, colors)
                        elif colors == 24:
                            bsize = (imgwidth*3 + 3) & 0xfffc # must read a multiple of 4 bytes
                            b = bytearray(bsize)
                            for row in range(height - skip - 1, -1, -1):
                                n = f.readinto(b)
                                if n != bsize:
                                    break
                                mytft.drawBitmap(0, row, imgwidth, 1, b, colors)
                    mytft.fillRectangle(0, 0, width - 1, row, (0, 0, 0))
            elif mode == "data": # raw 24 bit format with rgb data (gimp export type data)
                b = bytearray(width * 3)
                imgheight = os.stat(name)[6] // (width * 3)
                skip = (height - imgheight) // 2
                if skip > 0:
                    mytft.fillRectangle(0, 0, width - 1, skip, (0, 0, 0))
                else:
                    skip = 0
                for row in range(skip, height):
                    n = f.readinto(b)
                    if not n:
                        break
                    tft.TFT_io.swapcolors(b, width * 3)
                    mytft.drawBitmap(0, row, width, 1, b, 24)
                mytft.fillRectangle(0, row, width - 1, height - 1, (0, 0, 0))
        mytft.backlight(100)
    except FileNotFoundError:
        mytft.clrSCR()

PIR_flag = False

def callback(line):
    global PIR_flag
    PIR_flag = True

def tft_standby(mytft): # switch power off & ports to input
    mytft.backlight(False) # light off
    mytft.power(False)  # power off
    for pin_name in ["X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8", "X11", "X12",
           "Y1", "Y2", "Y5", "Y6", "Y7", "Y8", "Y11", "Y12",
           "X17", "X18", "X20", "X21", "X22"]:
        pin = pyb.Pin(pin_name, pyb.Pin.IN, pyb.Pin.PULL_DOWN) # set as input to save power

    for pin_name in ["X9", "X10", "Y9", "Y10"]:
        pin = pyb.Pin(pin_name, pyb.Pin.IN, pyb.Pin.PULL_UP) # set as input to save power


def main(v_flip = False, h_flip = False):

    global PIR_flag

## The 9 inch board has X19/X20 swapped. For this board, use the alternative code
    if TFT_SIZE == 9:
        adc = pyb.ADC(pyb.Pin.board.X19)  # read battery voltage (large PCB)
    else:
        adc = pyb.ADC(pyb.Pin.board.X20)  # read battery voltage
    vbus = pyb.Pin('USB_VBUS')
    if vbus.value():
        USBSUPPLY = True
    else:
        USBSUPPLY = False

    usb = pyb.USB_VCP()

    batval = adc.read()
    if (TOOLOWBAT < batval < LOWBAT) and USBSUPPLY == False: # low battery, switch off
        while True: # stay there until reset
            pyb.stop()  # go to sleep. Only the PIR Sensor may wake me up
# Battery OK, or suppy by USB, start TFT.
    if TFT_SIZE == 7:
        mytft = tft.TFT("SSD1963", "AT070TN92", tft.PORTRAIT, v_flip, h_flip)
    elif TFT_SIZE == 4:
        mytft = tft.TFT("SSD1963", "LB04301", tft.LANDSCAPE, v_flip, h_flip)
    elif TFT_SIZE == 9:
        mytft = tft.TFT("SSD1963", "AT090TN10", tft.PORTRAIT, False, True)
    mytft.clrSCR()
    width, height = mytft.getScreensize()
    
    if TFT_SIZE == 9:
## The 9 inch board has X19/X20 swapped. For this board, use the alternative code
        extint = pyb.ExtInt(pyb.Pin.board.X20, pyb.ExtInt.IRQ_RISING, pyb.Pin.PULL_NONE, callback) ## large PCB
    else:
        extint = pyb.ExtInt(pyb.Pin.board.X19, pyb.ExtInt.IRQ_RISING, pyb.Pin.PULL_NONE, callback)
    extint.enable()

    total_cnt = 0

    if TFT_SIZE == 4:
        os.chdir("img_272x480")
    else:
        os.chdir("img_480x800")
    files = os.listdir(".")

    start = COUNTER  # reset timer once
    PIR_flag = False

    while True:
        TESTMODE = usb.isconnected()  # On USB, run test mode
        while True:  # get the next file name, but not banner.bmp
            myrng = pyb.rng()
            name = files[myrng % len(files)]
            if name != BANNER_NAME:
                break

        batval = adc.read()
        if TESTMODE:
            print("Battery: ", batval, ", Files: ", len(files), ", File: ", name, ", RNG: ", myrng)

# test for low battery, switch off, or total count reached
        if (TOOLOWBAT < batval < LOWBAT) and USBSUPPLY == False:
            tft_standby(mytft)
            while True: # stay there until reset
                pyb.stop()

        if (total_cnt % BANNER_COUNTER) == 0:
            displayfile(mytft, BANNER_NAME, width, height)
            mytft.setTextPos(0, 0)
            if LOWBAT <= batval < WARNBAT:
                textcolor = (255,255,0)
            elif TOOLOWBAT < batval < LOWBAT:
                textcolor = (255,0,0)
            else: 
                textcolor = (0,255,0)
            mytft.setTextStyle(textcolor, None, 0, font14)
            mytft.printString("{:.3}V - {} - {}".format(((batval * 3.3 * SCALING) / 4096) + OFFSET, batval, total_cnt))
            pyb.delay(BANNER_TIME)

        total_cnt += 1
        displayfile(mytft, name, width, height)
        pyb.delay(PICT_TIME)

        if PIR_flag == False: ## For one picture activity, check inactivity counter
            start -= 1
            if start <= 0 or total_cnt > TOTAL_COUNTER:  # no activity,  long enough
                if TESTMODE == False:
                    tft_standby(mytft) # switch TFT off and ports inactive
                    pyb.delay(200)
                    pyb.stop()  # go to sleep Only PIR Sensor may wake me up
                    pyb.hard_reset() # will do all the re-init
                else:
                    print("Should switch off here for a second")
                    mytft.clrSCR()
                    mytft.setTextStyle((255,255,255), None, 0, font14)
                    mytft.setTextPos(0, 0)
                    pyb.delay(100)
                    batval = adc.read()
                    mytft.printString("{:.3}V - {}".format(((batval * 3.3 * SCALING) / 4096) + OFFSET, total_cnt))
                    mytft.printNewline()
                    mytft.printCR()
                    mytft.printString("Should switch off here for a second")
                    pyb.delay(3000)
                    if total_cnt > TOTAL_COUNTER:
                        total_cnt = 0
                PIR_flag = False
                start = COUNTER  # reset timer
        else: # activity. restart counter
            PIR_flag = False
            start = COUNTER  # reset timer

main()

