# 
# The MIT License (MIT)
# 
# Copyright (c) 2016 Robert Hammelrath
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# Class supporting TFT LC-displays with a parallel Interface
# First example: Controller SSD1963
# It uses X1..X8 for data and Y3, Y9, Y10, Y11 and Y12 for control signals.
# The minimal connection just for writes is X1..X8 for data, Y9 for /Reset. Y11 for /WR and Y12 for /RS
# Then LED and /CS must be hard tied to Vcc and GND, and /RD is not used.
#
#  Some parts of the software are a port of code provided by Rinky-Dink Electronics, Henning Karlsen,
#  with the following copyright notice:
## Copyright (C)2015 Rinky-Dink Electronics, Henning Karlsen. All right reserved
##  This library is free software; you can redistribute it and/or
##  modify it under the terms of the CC BY-NC-SA 3.0 license.
##  Please see the included documents for further information.
#

import pyb, stm
from uctypes import addressof

# define constants
#
RESET  = const(1 << 10)  ## Y9
RD     = const(1 << 11)  ## Y10
WR     = const(0x01)  ## Y11
D_C    = const(0x02)  ## Y12

LED    = const(1 << 8) ## Y3
POWER  = const(1 << 9) ## Y4

## CS is not used and must be hard tied to GND

PORTRAIT = const(1)
LANDSCAPE = const(0)

class TFT:
    
    def __init__(self, controller = "SSD1963", lcd_type = "LB04301", orientation = LANDSCAPE,  v_flip = False, h_flip = False):
        self.tft_init(controller, lcd_type, orientation, v_flip, h_flip)
    
    def tft_init(self, controller = "SSD1963", lcd_type = "LB04301", orientation = LANDSCAPE,  v_flip = False, h_flip = False):
#
# For convenience, define X1..X1 and Y9..Y12 as output port using thy python functions.
# X1..X8 will be redefind on the fly as Input by accessing the MODER control registers 
# when needed. Y9 is treate seperately, since it is used for Reset, which is done at python level
# since it need long delays anyhow, 5 and 15 ms vs. 10 µs.
#
# Set TFT geenral defaults
        self.controller = controller
        self.lcd_type = lcd_type
        self.orientation = orientation
        self.v_flip = v_flip # flip vertical
        self.h_flip = h_flip # flip horizontal
        self.c_flip = 0 # flip blue/red
        self.rc_flip = 0 # flip row/column (does not seem to work)
        
        self.setColor((255, 255, 255)) # set FG color to white as can be.
        self.setBGColor((0, 0, 0))     # set BG to black
# special treat for BG LED
        self.pin_led = pyb.Pin("Y3", pyb.Pin.OUT_PP)
        self.led_tim = pyb.Timer(4, freq=500)
        self.led_ch = self.led_tim.channel(3, pyb.Timer.PWM, pin=self.pin_led)
        self.led_ch.pulse_width_percent(0)  # led off
        self.pin_led.value(0)  ## switch BG LED off
# special treat for Power Pin
        self.pin_power = pyb.Pin("Y4", pyb.Pin.OUT_PP)
        self.pin_power.value(1)  ## switch Power on
        pyb.delay(10)
# this may have to be moved to the controller specific section
        if orientation == PORTRAIT:
            self.setXY = self.setXY_P
        else:
            self.setXY = self.setXY_L
# ----------        
        for pin_name in ["X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8", 
                   "Y10", "Y11", "Y12"]:
            pin = pyb.Pin(pin_name, pyb.Pin.OUT_PP) # set as output
            pin.value(1)  ## set high as default
# special treat for Reset
        self.pin_reset = pyb.Pin("Y9", pyb.Pin.OUT_PP)
# Reset the device
        self.pin_reset.value(1)  ## do a hard reset
        pyb.delay(10)
        self.pin_reset.value(0)  ## Low
        pyb.delay(20)
        self.pin_reset.value(1)  ## set high again
        pyb.delay(20)
#
# Now initialiize the LCD
# This is for the SSD1963 controller and two specific LCDs. More may follow.
# Data taken from the SSD1963 data sheet, SSD1963 Application Note and the LCD Data sheets
#
        if controller == "SSD1963":           # 1st approach for 480 x 272
            self.tft_cmd_data(0xe2, bytearray(b'\x1d\x02\x54'), 3) # PLL multiplier, set PLL clock to 100M
              # N=0x2D for 6.5MHz, 0x1D for 10MHz crystal 
              # PLLClock = Crystal * (Mult + 1) / (Div + 1)
              # The intermediate value Crystal * (Mult + 1) must be between 250MHz and 750 MHz
            self.tft_cmd_data(0xe0, bytearray(b'\x01'), 1) # PLL Enable
            pyb.delay(10)
            self.tft_cmd_data(0xe0, bytearray(b'\x03'), 1)
            pyb.delay(10)
            self.tft_cmd(0x01)                     # software reset
            pyb.delay(10)
#
# Settings for the LCD
# 
# The LCDC_FPR depends on PLL clock and the reccomended LCD Dot clock DCLK
#
# LCDC_FPR = (DCLK * 1048576 / PLLClock) - 1 
# 
# The other settings are less obvious, since the definitions of the SSD1963 data sheet and the 
# LCD data sheets differ. So what' common, even if the names may differ:
# HDP  Horizontal Panel width (also called HDISP, Thd). The value store in the register is HDP - 1
# VDP  Vertical Panel Width (also called VDISP, Tvd). The value stored in the register is VDP - 1
# HT   Total Horizontal Period, also called HP, th... The exact value does not matter
# VT   Total Vertical Period, alco called VT, tv, ..  The exact value does not matter
# HPW  Width of the Horizontal sync pulse, also called HS, thpw. 
# VPW  Width of the Vertical sync pulse, also called VS, tvpw
# Front Porch (HFP and VFP) Time between the end of display data and the sync pulse
# Back Porch (HBP  and VBP Time between the start of the sync pulse and the start of display data.
#      HT = FP + HDP + BP  and VT = VFP + VDP + VBP (sometimes plus sync pulse width)
# Unfortunately, the controller does not use these front/back porch times, instead it uses an starting time
# in the front porch area and defines (see also figures in chapter 13.3 of the SSD1963 data sheet)
# HPS  Time from that horiz. starting point to the start of the horzontal display area
# LPS  Time from that horiz. starting point to the horizontal sync pulse
# VPS  Time from the vert. starting point to the first line
# FPS  Time from the vert. starting point to the vertical sync pulse
#
# So the following relations must be held:
#
# HT >  HDP + HPS
# HPS >= HPW + LPS 
# HPS = Back Porch - LPS, or HPS = Horizontal back Porch
# VT > VDP + VPS
# VPS >= VPW + FPS
# VPS = Back Porch - FPS, or VPS = Vertical back Porch
#
# LPS or FPS may have a value of zero, since the length of the front porch is detemined by the 
# other figures
#
# The best is to start with the recomendations of the lCD data sheet for Back porch, grab a
# sync pulse with and the determine the other, such that they meet the relations. Typically, these
# values allow for some ambuigity. 
# 
            if lcd_type == "LB04301":  # Size 480x272, 4.3", 24 Bit, 4.3"
                #
                # Value            Min    Typical   Max
                # DotClock        5 MHZ    9 MHz    12 MHz
                # HT (Hor. Total   490     531      612
                # HDP (Hor. Disp)          480
                # HBP (back porch)  8      43
                # HFP (Fr. porch)   2       8
                # HPW (Hor. sync)   1
                # VT (Vert. Total) 275     288      335
                # VDP (Vert. Disp)         272
                # VBP (back porch)  2       12
                # VFP (fr. porch)   1       4
                # VPW (vert. sync)  1       10
                #
                # This table in combination with the relation above leads to the settings:
                # HPS = 43, HPW = 8, LPS = 0, HT = 531
                # VPS = 14, VPW = 10, FPS = 0, VT = 288
                #
                self.disp_x_size = 479
                self.disp_y_size = 271
                self.tft_cmd_data_AS(0xe6, bytearray(b'\x01\x70\xa3'), 3) # PLL setting for PCLK
                    # (9MHz * 1048576 / 100MHz) - 1 = 94371 = 0x170a3
                self.tft_cmd_data_AS(0xb0, bytearray(  # # LCD SPECIFICATION
                    [0x20,                # 24 Color bits, HSync/VSync low, No Dithering
                     0x00,                # TFT mode
                     self.disp_x_size >> 8, self.disp_x_size & 0xff, # physical Width of TFT
                     self.disp_y_size >> 8, self.disp_y_size & 0xff, # physical Height of TFT
                     0x00]), 7)  # Last byte only required for a serial TFT
                self.tft_cmd_data_AS(0xb4, bytearray(b'\x02\x13\x00\x2b\x08\x00\x00\x00'), 8) 
                        # HSYNC,  Set HT 531  HPS 43   HPW=Sync pulse 8 LPS 0
                self.tft_cmd_data_AS(0xb6, bytearray(b'\x01\x20\x00\x0e\x0a\x00\x00'), 7) 
                        # VSYNC,  Set VT 288  VPS 14 VPW 10 FPS 0
                self.tft_cmd_data_AS(0x36, bytearray([(orientation & 1) << 5 | (h_flip & 1) << 1 | (v_flip) & 1]), 1) 
                        # rotation/ flip, etc., t.b.d. 
            elif lcd_type == "AT070TN92": # Size 800x480, 7", 18 Bit, lower color bits ignored
                #
                # Value            Min     Typical   Max
                # DotClock       26.4 MHz 33.3 MHz  46.8 MHz
                # HT (Hor. Total   862     1056     1200
                # HDP (Hor. Disp)          800
                # HBP (back porch)  46      46       46
                # HFP (Fr. porch)   16     210      254
                # HPW (Hor. sync)   1                40
                # VT (Vert. Total) 510     525      650
                # VDP (Vert. Disp)         480
                # VBP (back porch)  23      23       23
                # VFP (fr. porch)   7       22      147
                # VPW (vert. sync)  1                20
                #
                # This table in combination with the relation above leads to the settings:
                # HPS = 46, HPW = 8,  LPS = 0, HT = 1056
                # VPS = 23, VPW = 10, VPS = 0, VT = 525
                #
                self.disp_x_size = 799
                self.disp_y_size = 479
                self.tft_cmd_data_AS(0xe6, bytearray(b'\x05\x53\xf6'), 3) # PLL setting for PCLK
                    # (33.3MHz * 1048576 / 100MHz) - 1 = 349174 = 0x553f6
                self.tft_cmd_data_AS(0xb0, bytearray(  # # LCD SPECIFICATION
                    [0x00,                # 18 Color bits, HSync/VSync low, No Dithering/FRC
                     0x00,                # TFT mode
                     self.disp_x_size >> 8, self.disp_x_size & 0xff, # physical Width of TFT
                     self.disp_y_size >> 8, self.disp_y_size & 0xff, # physical Height of TFT
                     0x00]), 7)  # Last byte only required for a serial TFT
                self.tft_cmd_data_AS(0xb4, bytearray(b'\x04\x1f\x00\x2e\x08\x00\x00\x00'), 8) 
                        # HSYNC,      Set HT 1056  HPS 46  HPW 8 LPS 0
                self.tft_cmd_data_AS(0xb6, bytearray(b'\x02\x0c\x00\x17\x08\x00\x00'), 7) 
                        # VSYNC,   Set VT 525  VPS 23 VPW 08 FPS 0
                self.tft_cmd_data_AS(0x36, bytearray([(orientation & 1) << 5 | (h_flip & 1) << 1 | (v_flip) & 1]), 1) 
                        # rotation/ flip, etc., t.b.d. 
            else:
                print("Wrong Parameter lcd_type: ", lcd_type)
                return
            self.tft_cmd_data_AS(0xBA, bytearray(b'\x0f'), 1) # GPIO[3:0] out 1
            self.tft_cmd_data_AS(0xB8, bytearray(b'\x07\x01'), 1) # GPIO3=input, GPIO[2:0]=output

            self.tft_cmd_data_AS(0xf0, bytearray(b'\x00'), 1) # Pixel data Interface 8 Bit

            self.tft_cmd(0x29)             # Display on
            self.tft_cmd_data_AS(0xbe, bytearray(b'\x06\xf0\x01\xf0\x00\x00'), 6) 
                    # Set PWM for B/L
            self.tft_cmd_data_AS(0xd0, bytearray(b'\x0d'), 1) # Set DBC: enable, agressive
        else:
            print("Wrong Parameter controller: ", controller)
            return
#
# Set character printing defaults
#
        self.setTextPos(0,0)
        self.setTextStyle(None, None, 0, None, 0)
#
# Init done. clear Screen and switch BG LED on
#
        self.clrSCR()           # clear the display
#        self.backlight(100)  ## switch BG LED on
#
# Return screen dimensions
#
    def getScreensize(self):
        if self.orientation == LANDSCAPE:
            return (self.disp_x_size + 1, self.disp_y_size + 1)
        else:
            return (self.disp_y_size + 1, self.disp_x_size + 1)
#
# set backlight brightness
#            
    def backlight(self, percent):
        percent = max(0, min(percent, 100))
        self.led_ch.pulse_width_percent(percent)  # set LED
#
# switch power on/off
#            
    def power(self, onoff):
        if onoff:
            self.pin_power.value(True)  ## switch power on or off
        else:
            self.pin_power.value(False)

#
# set the tft flip modes
#            
    def set_tft_mode(self, v_flip = False, h_flip = False, c_flip = False, orientation = LANDSCAPE):
        self.v_flip = v_flip # flip vertical
        self.h_flip = h_flip # flip horizontal
        self.c_flip = c_flip # flip blue/red
        self.orientation = orientation # LANDSCAPE/PORTRAIT
        self.tft_cmd_data_AS(0x36, 
            bytearray([(self.orientation << 5) |(self.c_flip << 3) | (self.h_flip & 1) << 1 | (self.v_flip) & 1]), 1) 
                        # rotation/ flip, etc., t.b.d. 
#
# get the tft flip modes
#            
    def get_tft_mode(self):
        return (self.v_flip, self.h_flip, self.c_flip, self.orientation) # 
#
# set the color used for the draw commands
#            
    def setColor(self, fgcolor):
        self.color = fgcolor
        self.colorvect = bytearray(self.color)  # prepare byte array
#
# Set BG color used for the draw commands
# 
    def setBGColor(self, bgcolor):
        self.BGcolor = bgcolor
        self.BGcolorvect = bytearray(self.BGcolor)  # prepare byte array
#
# get the color used for the draw commands
#            
    def getColor(self):
        return self.color
#
# get BG color used for 
# 
    def getBGColor(self):
        return self.BGcolor
#
# Set text position
#
    def setTextPos(self, x, y, rel = False):
        self.text_width, self.text_height = self.getScreensize()
        self.text_x = x
        if rel: # relative line
            self.text_y = (y + self.scroll_start) % self.text_height
        else:  # absolute
            self.text_y = y
#
# Get text position
#
    def getTextPos(self):
        return (self.text_x, self.text_y)
#
# Set Text Style
#
    def setTextStyle(self, fgcolor = None, bgcolor = None, transparency = None, font = None, gap = None):
        if font != None:
            self.text_font = font 
        if font:
            self.text_rows, self.text_cols, nchar, first = font.get_properties() # 
        if transparency != None:
            self.transparency = transparency
        if gap != None:
            self.text_gap = gap
        self.text_color = bytearray(0)
        if bgcolor != None:
            self.text_color += bytearray(bgcolor)
        else:
            self.text_color += self.BGcolorvect
        if fgcolor != None:
            self.text_color += bytearray(fgcolor)
        else: 
            self.text_color += self.colorvect
        if transparency != None:
            self.transparency = transparency
        self.text_color  += bytearray([self.transparency])
        if gap != None:
            self.text_gap = gap
#
# Draw a single pixel at location x, y
# Rather slow at 40µs/Pixel
#        
    def drawPixel(self, x, y):
        self.setXY(x, y, x, y)
        self.displaySCR_AS(self.colorvect, 1)  # 
#
# clear screen, set it to BG color.
#             
    def clrSCR(self):
        self.clrXY()
        self.fillSCR_AS(self.BGcolorvect, (self.disp_x_size + 1) * (self.disp_y_size + 1))
        self.text_x = self.text_y = self.scroll_start = 0
        self.setScrollStart(0)
#
# Draw a line from x1, y1 to x2, y2 with the color set by setColor()
# Straight port from the UTFT Library at Rinky-Dink Electronics
# 
    def drawLine(self, x1, y1, x2, y2): 
        if y1 == y2:
            self.drawHLine(x1, y1, x2 - x1 + 1)
        elif x1 == x2:
            self.drawVLine(x1, y1, y2 - y1 + 1)
        else:
            dx, xstep  = (x2 - x1, 1) if x2 > x1 else (x1 - x2, -1)
            dy, ystep  = (y2 - y1, 1) if y2 > y1 else (y1 - y2, -1)
            col, row = x1, y1
            if dx < dy:
                t = - (dy >> 1)
                while True:
                    self.drawPixel(col, row)
                    if row == y2:
                        return
                    row += ystep
                    t += dx
                    if t >= 0:
                        col += xstep
                        t -= dy
            else:
                t = - (dx >> 1)
                while True:
                    self.drawPixel(col, row)
                    if col == x2:
                        return
                    col += xstep
                    t += dy
                    if t >= 0:
                        row += ystep
                        t -= dx
#
# Draw a horizontal line with 1 Pixel width, from x,y to x + l - 1, y
# Straight port from the UTFT Library at Rinky-Dink Electronics
# 
    def drawHLine(self, x, y, l): # draw horiontal Line
        if l < 0:  # negative length, swap parameters
            l = -l
            x -= l
        self.setXY(x, y, x + l - 1, y) # set display window
        self.fillSCR_AS(self.colorvect, l)
#
# Draw a vertical line with 1 Pixel width, from x,y to x, y + l - 1
# Straight port from the UTFT Library at Rinky-Dink Electronics
# 
    def drawVLine(self, x, y, l): # draw horiontal Line
        if l < 0:  # negative length, swap parameters
            l = -l
            y -= l
        self.setXY(x, y, x, y + l - 1) # set display window
        self.fillSCR_AS(self.colorvect, l)
#
# Draw rectangle from x1, y1, to x2, y2
# Straight port from the UTFT Library at Rinky-Dink Electronics
#
    def drawRectangle(self, x1, y1, x2, y2):
        if x1 > x2:
            t = x1; x1 = x2; x2 = t
        if y1 > y2:
            t = y1; y1 = y2; y2 = t
    	self.drawHLine(x1, y1, x2 - x1 + 1)
        self.drawHLine(x1, y2, x2 - x1 + 1)
        self.drawVLine(x1, y1, y2 - y1 + 1)
        self.drawVLine(x2, y1, y2 - y1 + 1)
#
# Fill rectangle
# Straight port from the UTFT Library at Rinky-Dink Electronics
#
    def fillRectangle(self, x1, y1, x2, y2):
        if x1 > x2:
            t = x1; x1 = x2; x2 = t
        if y1 > y2:
            t = y1; y1 = y2; y2 = t
        self.setXY(x1, y1, x2, y2) # set display window
        self.fillSCR_AS(self.colorvect, (x2 - x1 + 1) * (y2 - y1 + 1))

#
# Draw smooth rectangle from x1, y1, to x2, y2
# Straight port from the UTFT Library at Rinky-Dink Electronics
#
    def drawClippedRectangle(self, x1, y1, x2, y2):
        if x1 > x2:
            t = x1; x1 = x2; x2 = t
        if y1 > y2:
            t = y1; y1 = y2; y2 = t
        if (x2-x1) > 4 and (y2-y1) > 4:
            self.drawPixel(x1 + 2,y1 + 1)
            self.drawPixel(x1 + 1,y1 + 2)
            self.drawPixel(x2 - 2,y1 + 1)
            self.drawPixel(x2 - 1,y1 + 2)
            self.drawPixel(x1 + 2,y2 - 1)
            self.drawPixel(x1 + 1,y2 - 2)
            self.drawPixel(x2 - 2,y2 - 1)
            self.drawPixel(x2 - 1,y2 - 2)
            self.drawHLine(x1 + 3, y1, x2 - x1 - 5)
            self.drawHLine(x1 + 3, y2, x2 - x1 - 5)
            self.drawVLine(x1, y1 + 3, y2 - y1 - 5)
            self.drawVLine(x2, y1 + 3, y2 - y1 - 5)
#
# Fill smooth rectangle from x1, y1, to x2, y2
# Straight port from the UTFT Library at Rinky-Dink Electronics
#
    def fillClippedRectangle(self, x1, y1, x2, y2):
        if x1 > x2:
            t = x1; x1 = x2; x2 = t
        if y1 > y2:
            t = y1; y1 = y2; y2 = t
        if (x2-x1) > 4 and (y2-y1) > 4:
            for i in range(((y2 - y1) // 2) + 1):
                if i == 0:
                    self.drawHLine(x1 + 3, y1 + i, x2 - x1 - 5)
                    self.drawHLine(x1 + 3, y2 - i, x2 - x1 - 5)
                elif i == 1:
                    self.drawHLine(x1 + 2, y1 + i, x2 - x1 - 3)
                    self.drawHLine(x1 + 2, y2 - i, x2 - x1 - 3)
                elif i == 2:
                    self.drawHLine(x1 + 1, y1 + i, x2 - x1 - 1)
                    self.drawHLine(x1 + 1, y2 - i, x2 - x1 - 1)
                else:
                    self.drawHLine(x1, y1 + i, x2 - x1 + 1)
                    self.drawHLine(x1, y2 - i, x2 - x1 + 1)
#
# draw a circle at x, y with radius
# Straight port from the UTFT Library at Rinky-Dink Electronics
#
    def drawCircle(self, x, y, radius):
    
        f = 1 - radius
        ddF_x = 1
        ddF_y = -2 * radius
        x1 = 0
        y1 = radius

        self.drawPixel(x, y + radius)
        self.drawPixel(x, y - radius)
        self.drawPixel(x + radius, y)
        self.drawPixel(x - radius, y)

        while x1 < y1:
            if f >= 0:
	            y1 -= 1
	            ddF_y += 2
	            f += ddF_y
            x1 += 1
            ddF_x += 2
            f += ddF_x
            self.drawPixel(x + x1, y + y1)
            self.drawPixel(x - x1, y + y1)
            self.drawPixel(x + x1, y - y1)
            self.drawPixel(x - x1, y - y1)
            self.drawPixel(x + y1, y + x1)
            self.drawPixel(x - y1, y + x1)
            self.drawPixel(x + y1, y - x1)
            self.drawPixel(x - y1, y - x1)
#
# fill a circle at x, y with radius
# Straight port from the UTFT Library at Rinky-Dink Electronics
# Instead of caluclating x = sqrt(r*r - y*y), it searches the x
# for r*r = x*x + x*x
#
    def fillCircle(self, x, y, radius):
        r_square = radius * radius * 4
        for y1 in range (-(radius * 2), 1): 
            y_square = y1 * y1
            for x1 in range (-(radius * 2), 1):
                if x1*x1+y_square <= r_square: 
                    x1i = x1//2
                    y1i = y1//2
                    self.drawHLine(x + x1i, y + y1i, 2 * (-x1i))
                    self.drawHLine(x + x1i, y - y1i, 2 * (-x1i))
                    break;
#
# Draw a bitmap at x,y with size sx, sy
# mode determines the type of expected data
# mode = 0: The data must contain 3 bytes/pixel red/green/blue
# mode = 1: The data must contain 2 packed bytes/pixel blue/green/red in 565 format
# mode = 2: The data contains 1 bit per pixel, mapped to fg/bg color
#
    def drawBitmap(self, x, y, sx, sy, data, mode = 0):
        self.setXY(x, y, x + sx - 1, y + sy - 1)
        if mode == 0:
            self.displaySCR_AS(data, sx * sy)
        elif mode == 1:
            self.displaySCR565_AS(data, sx * sy)
        elif mode == 2:
            control = bytearray(self.BGcolorvect + self.colorvect + chr(self.transparency))
            self.displaySCR_bitmap(data, sx*sy, control, 0)
#
# set scroll area to the region between the first and last line
#
    def setScrollArea(self, tfa, vsa, bfa):
        self.tft_cmd_data_AS(0x33, bytearray(  #set scrolling range
                    [(tfa >> 8) & 0xff, tfa & 0xff, 
                     (vsa >> 8) & 0xff, vsa & 0xff,
                     (bfa >> 8) & 0xff, bfa & 0xff]), 6)
        self.scroll_fta = tfa
        self.scroll_vsa = vsa
        self.scroll_bfa = bfa
#
# set the line which is displayed first
#
    def setScrollStart(self, lline):
        self.tft_cmd_data_AS(0x37, bytearray([(lline >> 8) & 0xff, lline & 0xff]), 2)
        self.scroll_start = lline # store the logical first line
#
# Check, if a new line is to be opened
# if yes, advance, including scrolling, and clear line, if flags is set
#
    def printNewline(self):
        self.text_y += self.text_rows
        if (self.text_y + self.text_rows) > self.scroll_vsa: # does the line fit?
            self.text_y = 0
            newline = self.text_rows
            self.setScrollStart(newline)
        elif self.scroll_start > 0: # Scrolling has started
            newline = (self.scroll_start + self.text_rows) % self.scroll_vsa
            self.setScrollStart(newline)
#
# Carriage Return
#
    def printCR(self): # clear to end of line
        self.text_x = 0
#
# clear to end-of-line
#
    def printClrEOL(self): # clear to end of line
        self.setXY(self.text_x, self.text_y, 
                   self.text_width - self.text_x - 1, self.text_y + self.text_rows - 1) # set display window
        self.fillSCR_AS(self.text_color, self.text_width * self.text_rows)
#
# Print string s 
# 
    def printString(self, s, bg_buf = None):
        for c in s:
            self.printChar(c, bg_buf)
#
# Print string c using the given char bitmap at location x, y
# 
    def printChar(self, c, bg_buf = None):
# get the charactes pixel bitmap and dimensions
        fontptr, rows, cols = self.text_font.get_ch(ord(c))
        pix_count = cols * rows   # number of bits in the char
# test char fit
        if self.text_x + cols > self.text_width:  # does the char fit on the screen?
            self.printCR()      # No, then CR
            self.printNewline() # NL: advance to the next line
            self.printClrEOL()  # clear to end of line
# set data arrays & XY-Range
        if self.transparency: # in case of transpareny, the frame buffer content is needed
            if not bg_buf:    # buffer allocation needed?
                bg_buf = bytearray(pix_count * 3) # sigh...
            self.setXY(self.text_x, self.text_y, self.text_x + cols - 1, self.text_y + rows - 1) # set area
            self.tft_read_cmd_data_AS(0x2e, bg_buf, pix_count * 3) # read background data
        else:
            bg_buf = 0 # dummy assignment, since None is not accepted
# print char
        self.setXY(self.text_x, self.text_y, self.text_x + cols - 1, self.text_y + rows - 1) # set area
        self.displaySCR_bitmap(fontptr, pix_count, self.text_color, bg_buf) # display char!
#advance pointer
        self.text_x += (cols + self.text_gap)
#
# display bitmap
#
    @staticmethod
    @micropython.viper        
    def displaySCR_bitmap(bits: ptr8, size: int, control: ptr8, bg_buf: ptr8):
        gpioa = ptr8(stm.GPIOA)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        gpioam = ptr16(stm.GPIOA + stm.GPIO_MODER)
#
        transparency = control[6]
        bm_ptr = 0
        bg_ptr = 0
        mask   = 0x80
#        rd_command = 0x2e  ## start read
        while size:
#           if False: # transparency: # read back data
#               gpioa[stm.GPIO_ODR] = rd_command         # start/continue read command
#               gpiob[1] = D_C | WR     # set C/D and WR low
#               gpiob[0] = D_C | WR     # set C/D and WR high

#               gpioam[0] = 0       # configure X1..X8 as Input

#               gpiob[1] = RD       # set RD low. C/D still high
#               rd_command = 0x3e      # continue read
#               bg_red = gpioa[stm.GPIO_IDR]  # get data from port A
#               gpiob[0] = RD       # set RD high again

#               gpiob[1] = RD       # set RD low. C/D still high
#               delay = 1
#               bg_green = gpioa[stm.GPIO_IDR]  # get data from port A
#               gpiob[0] = RD       # set RD high again

#               gpiob[1] = RD       # set RD low. C/D still high
#               delay = 1
#               bg_blue = gpioa[stm.GPIO_IDR]  # get data from port A
#               gpiob[0] = RD       # set RD high again

#               gpioam[0] = 0x5555  # configure X1..X8 as Output

#               gpioa[stm.GPIO_ODR] = 0x3c         # continue write command
#               gpiob[1] = D_C | WR     # set C/D and WR low
#               gpiob[0] = D_C | WR     # set C/D and WR high

            if bits[bm_ptr] & mask:
                if transparency & 8: # Invert bg color as foreground
                    gpioa[stm.GPIO_ODR] = 255 - bg_buf[bg_ptr] # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = 255 - bg_buf[bg_ptr + 1]  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = 255 - bg_buf[bg_ptr + 2]  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again
                else: # not invert
                    gpioa[stm.GPIO_ODR] = control[3]     # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = control[4]      # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = control[5]      # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again
            else:
                if transparency & 1: # Dim background
                    gpioa[stm.GPIO_ODR] = bg_buf[bg_ptr] >> 1  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = bg_buf[bg_ptr + 1] >> 1  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = bg_buf[bg_ptr + 2] >> 1  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again
                elif transparency & 2: # keep Background
                    gpioa[stm.GPIO_ODR] = bg_buf[bg_ptr] # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = bg_buf[bg_ptr + 1]  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = bg_buf[bg_ptr + 2]  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again
                elif transparency & 4: # invert Background
                    gpioa[stm.GPIO_ODR] = 255 - bg_buf[bg_ptr] # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = 255 - bg_buf[bg_ptr + 1]  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = 255 - bg_buf[bg_ptr + 2]  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again
                else: # not transparent
                    gpioa[stm.GPIO_ODR] = control[0]  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = control[1]  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again

                    gpioa[stm.GPIO_ODR] = control[2]  # set data on port A
                    gpiob[1] = WR       # set WR low. C/D still high
                    gpiob[0] = WR       # set WR high again
            mask >>= 1
            if mask == 0: # map ptr advance on byte exhaust
                mask = 0x80
                bm_ptr += 1
            size -= 1
            bg_ptr += 3
#
# Set the address range for various draw commands and set the TFT for expecting data
#
    @staticmethod
    @micropython.viper        
    def setXY_P(x1: int, y1: int, x2: int, y2: int): ## set the adress range, Portrait
# set column address
        gpioa = ptr8(stm.GPIOA + stm.GPIO_ODR)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        gpioa[0] = 0x2b         # command
        gpiob[1] = D_C | WR     # set C/D and WR low
        gpiob[0] = D_C | WR     # set C/D and WR high

        gpioa[0] = x1 >> 8  # high byte of x1
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = x1 & 0xff# low byte of x1
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = x2 >> 8  # high byte of x2
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = x2 & 0xff# low byte of x2
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again
# set row address            
        gpioa[0] = 0x2a         # command
        gpiob[1] = D_C | WR     # set C/D and WR low
        gpiob[0] = D_C | WR     # set C/D and WR high

        gpioa[0] = y1 >> 8  # high byte of x1
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = y1 & 0xff# low byte of x1
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = y2 >> 8  # high byte of x2
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = y2 & 0xff# low byte of x2
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = 0x2c         # Start data entry
        gpiob[1] = D_C | WR     # set C/D and WR low
        gpiob[0] = D_C | WR     # set C/D and WR high

    @staticmethod
    @micropython.viper        
    def setXY_L(x1: int, y1: int, x2: int, y2: int): ## set the adress range, Landscape
# set column address
        gpioa = ptr8(stm.GPIOA + stm.GPIO_ODR)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        gpioa[0] = 0x2a         # command
        gpiob[1] = D_C | WR     # set C/D and WR low
        gpiob[0] = D_C | WR     # set C/D and WR high

        gpioa[0] = x1 >> 8  # high byte of x1
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = x1 & 0xff# low byte of x1
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = x2 >> 8  # high byte of x2
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = x2 & 0xff# low byte of x2
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again
# set row address            
        gpioa[0] = 0x2b         # command
        gpiob[1] = D_C | WR     # set C/D and WR low
        gpiob[0] = D_C | WR     # set C/D and WR high

        gpioa[0] = y1 >> 8  # high byte of x1
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = y1 & 0xff# low byte of x1
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = y2 >> 8  # high byte of x2
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = y2 & 0xff# low byte of x2
        gpiob[1] = WR       # set WR low. C/D still high
        gpiob[0] = WR       # set WR high again

        gpioa[0] = 0x2c         # Start data entry
        gpiob[1] = D_C | WR     # set C/D and WR low
        gpiob[0] = D_C | WR     # set C/D and WR high
#
# reset the address range to fullscreen
#       
    def clrXY(self):
        if self.orientation == LANDSCAPE:
            self.setXY(0, 0, self.disp_x_size, self.disp_y_size)
        else:
            self.setXY(0, 0, self.disp_y_size, self.disp_x_size)
#
# Fill screen by writing size pixels with the color given in data
# data must be 3 bytes of red, green, blue
# The area to be filled has to be set in advance by setXY
# The speed is about 440 ns/pixel
#
    @staticmethod
    @micropython.viper        
    def fillSCR(data: ptr8, size: int):
        gpioa = ptr8(stm.GPIOA + stm.GPIO_ODR)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        while size:
            gpioa[0] = data[0]  # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again

            gpioa[0] = data[1]  # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again

            gpioa[0] = data[2]  # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again
            size -= 1
#
# Display screen by writing size pixels with the data
# data must contains size triplets of red, green and blue data values
# The area to be filled has to be set in advance by setXY
# The speed is about 650 ns/pixel
#
    @staticmethod
    @micropython.viper        
    def displaySCR(data: ptr8, size: int):
        gpioa = ptr8(stm.GPIOA + stm.GPIO_ODR)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        ptr = 0
        while size:
            gpioa[0] = data[ptr]  # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again

            gpioa[0] = data[ptr + 1]  # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again

            gpioa[0] = data[ptr + 2]  # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again
            ptr += 3
            size -= 1
#
# Display screen by writing size pixels with the data
# data must contains size packed words of red, green and blue data values
# The area to be filled has to be set in advance by setXY
# The speed is about 650 ns/pixel
#
    @staticmethod
    @micropython.viper        
    def displaySCR565(data: ptr8, size: int):
        gpioa = ptr8(stm.GPIOA + stm.GPIO_ODR)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        ptr = 0
        while size:
            gpioa[0] = data[ptr] & 0xf8  # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again

            gpioa[0] = (data[ptr] << 5 | (data[ptr + 1] >> 3) & 0xfc) # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again

            gpioa[0] = (data[ptr + 1] << 3) # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again
            ptr += 2
            size -= 1
#
# Assembler version of 
# Fill screen by writing size pixels with the color given in data
# data must be 3 bytes of red, green, blue
# The area to be filled has to be set in advance by setXY
# The speed is about 214 ns/pixel
#
    @staticmethod
    @micropython.asm_thumb
    def fillSCR_AS(r0, r1):  # r0: ptr to data, r1: number of pixels (3 bytes/pixel)
# set up pointers to GPIO
# r5: bit mask for control lines
# r6: GPIOA OODR register ptr
# r7: GPIOB BSSRL register ptr
        mov(r5, WR)
        movwt(r6, stm.GPIOA) # target
        add (r6, stm.GPIO_ODR)
        movwt(r7, stm.GPIOB)
        add (r7, stm.GPIO_BSRRL)
        ldrb(r2, [r0, 0])  # red   
        ldrb(r3, [r0, 1])  # green
        ldrb(r4, [r0, 2])  # blue
        b(loopend)

        label(loopstart)
        strb(r2, [r6, 0])  # Store red
        strb(r5, [r7, 2])  # WR low
#        nop()
        strb(r5, [r7, 0])  # WR high

        strb(r3, [r6, 0])  # store blue
        strb(r5, [r7, 2])  # WR low
        nop()
        strb(r5, [r7, 0])  # WR high
        
        strb(r4, [r6, 0])  # store blue
        strb(r5, [r7, 2])  # WR low
#        nop()
        strb(r5, [r7, 0])  # WR high

        label(loopend)
        sub (r1, 1)  # End of loop?
        bpl(loopstart)
#
# Assembler version of:
# Fill screen by writing size pixels with the data
# data must contains size triplets of red, green and blue data values
# The area to be filled has to be set in advance by setXY
# the speed is 266 ns for a byte triple 
#
    @staticmethod
    @micropython.asm_thumb
    def displaySCR_AS(r0, r1):  # r0: ptr to data, r1: is number of pixels (3 bytes/pixel)
# set up pointers to GPIO
# r5: bit mask for control lines
# r6: GPIOA OODR register ptr
# r7: GPIOB BSSRL register ptr
        mov(r5, WR)
        movwt(r6, stm.GPIOA) # target
        add (r6, stm.GPIO_ODR)
        movwt(r7, stm.GPIOB)
        add (r7, stm.GPIO_BSRRL)
        b(loopend)

        label(loopstart)
        ldrb(r2, [r0, 0])  # red   
        strb(r2, [r6, 0])  # Store red
        strb(r5, [r7, 2])  # WR low
        strb(r5, [r7, 0])  # WR high

        ldrb(r2, [r0, 1])  # pre green
        strb(r2, [r6, 0])  # store greem
        strb(r5, [r7, 2])  # WR low
        strb(r5, [r7, 0])  # WR high
        
        ldrb(r2, [r0, 2])  # blue
        strb(r2, [r6, 0])  # store blue
        strb(r5, [r7, 2])  # WR low
        strb(r5, [r7, 0])  # WR high

        add (r0, 3)  # advance data ptr

        label(loopend)
        sub (r1, 1)  # End of loop?
        bpl(loopstart)
# Assembler version of:
# Fill screen by writing size pixels with the data
# data must contains size packed duplets of red, green and blue data values
# The area to be filled has to be set in advance by setXY
# the speed is 266 ns for a byte pixel 
#
    @staticmethod
    @micropython.asm_thumb
    def displaySCR565_AS(r0, r1):  # r0: ptr to data, r1: is number of pixels (3 bytes/pixel)
# set up pointers to GPIO
# r5: bit mask for control lines
# r6: GPIOA OODR register ptr
# r7: GPIOB BSSRL register ptr
        mov(r5, WR)
        movwt(r6, stm.GPIOA) # target
        add (r6, stm.GPIO_ODR)
        movwt(r7, stm.GPIOB)
        add (r7, stm.GPIO_BSRRL)
        b(loopend)

        label(loopstart)

        ldrb(r2, [r0, 0])  # red   
        mov (r3, 0xf8)     # mask out lower 3 bits
        and_(r2, r3)        
        strb(r2, [r6, 0])  # Store red
        strb(r5, [r7, 2])  # WR low
        strb(r5, [r7, 0])  # WR high

        ldrb(r2, [r0, 0])  # pre green
        mov (r3, 5)        # shift 5 bits up to 
        lsl(r2, r3)
        ldrb(r4, [r0, 1])  # get the next 3 bits
        mov (r3, 3)        # shift 3 to the right
        lsr(r4, r3)
        orr(r2, r4)        # add them to the first bits
        mov(r3, 0xfc)      # mask off the lower two bits
        and_(r2, r3)
        strb(r2, [r6, 0])  # store green
        strb(r5, [r7, 2])  # WR low
        strb(r5, [r7, 0])  # WR high
        
        ldrb(r2, [r0, 1])  # blue
        mov (r3, 3)
        lsl(r2, r3)
        strb(r2, [r6, 0])  # store blue
        strb(r5, [r7, 2])  # WR low
        strb(r5, [r7, 0])  # WR high
        
        add (r0, 2)  # advance data ptr

        label(loopend)

        sub (r1, 1)  # End of loop?
        bpl(loopstart)
#
# Send a command and data to the TFT controller
# cmd is the command byte, data must be a bytearray object with the command payload,
# int is the size of the data
# For the startup-phase use this function.
#
    @staticmethod
    @micropython.viper        
    def tft_cmd_data(cmd: int, data: ptr8, size: int):
        gpioa = ptr8(stm.GPIOA + stm.GPIO_ODR)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        gpioa[0] = cmd          # set data on port A
        gpiob[1] = D_C | WR     # set C/D and WR low
        gpiob[0] = D_C | WR     # set C/D and WR high
        for i in range(size):
            gpioa[0] = data[i]  # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again
#
# Assembler version of send command & data to the TFT controller
# data must be a bytearray object, int is the size of the data.
# The speed is about 120 ns/byte
#
    @staticmethod
    @micropython.asm_thumb
    def tft_cmd_data_AS(r0, r1, r2):  # r0: command, r1: ptr to data, r2 is size in bytes
# set up pointers to GPIO
# r5: bit mask for control lines
# r6: GPIOA OODR register ptr
# r7: GPIOB BSSRL register ptr
        movwt(r6, stm.GPIOA) # target
        add (r6, stm.GPIO_ODR)
        movwt(r7, stm.GPIOB)
        add (r7, stm.GPIO_BSRRL)
# Emit command byte
        mov(r5, WR | D_C)
        strb(r0, [r6, 0])  # set command byte
        strh(r5, [r7, 2])  # WR and D_C low
        strh(r5, [r7, 0])  # WR and D_C high
# now loop though data
        mov(r5, WR)
        b(loopend)

        label(loopstart)
        ldrb(r4, [r1, 0])  # load data   
        strb(r4, [r6, 0])  # Store data
        strh(r5, [r7, 2])  # WR low
        strh(r5, [r7, 0])  # WR high
        add (r1, 1)  # advance data ptr

        label(loopend)
        sub (r2, 1)  # End of loop?
        bpl(loopstart)
#
# Send a command to the TFT controller
#
    @staticmethod
    @micropython.viper        
    def tft_cmd(cmd: int):
        gpioa = ptr8(stm.GPIOA + stm.GPIO_ODR)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        gpioa[0] = cmd          # set data on port A
        gpiob[1] = D_C | WR     # set C/D and WR low
        gpiob[0] = D_C | WR     # set C/D and WR high
#
# Send data to the TFT controller
# data must be a bytearray object, int is the size of the data.
# the speed is about 460 ns/byte
#
    @staticmethod
    @micropython.viper        
    def tft_write_data(data: ptr8, size: int):
        gpioa = ptr8(stm.GPIOA + stm.GPIO_ODR)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        for i in range(size):
            gpioa[0] = data[i]  # set data on port A
            gpiob[1] = WR       # set WR low. C/D still high
            gpiob[0] = WR       # set WR high again
#
# Assembler version of send data to the TFT controller
# data must be a bytearray object, int is the size of the data.
# The speed is about 120 ns/byte
#
    @staticmethod
    @micropython.asm_thumb
    def tft_write_data_AS(r0, r1):  # r0: ptr to data, r1: is size in Bytes
# set up pointers to GPIO
# r5: bit mask for control lines
# r6: GPIOA OODR register ptr
# r7: GPIOB BSSRL register ptr
        movwt(r6, stm.GPIOA) # target
        add (r6, stm.GPIO_ODR)
        movwt(r7, stm.GPIOB)
        add (r7, stm.GPIO_BSRRL)
        mov(r5, WR)
# and go, first test size for 0
        b(loopend)
 
        label(loopstart)
        ldrb(r3, [r0, 0])  # load data   
        strb(r3, [r6, 0])  # Store data
        strh(r5, [r7, 2])  # WR low
        strh(r5, [r7, 0])  # WR high
       
        add (r0, 1)  # advance data ptr
        label(loopend)
        sub (r1, 1)  # End of loop?
        bpl(loopstart)
#
# Send a command to the TFT controller
#
    @staticmethod
    @micropython.viper        
    def tft_cmd(cmd: int):
        gpioa = ptr8(stm.GPIOA + stm.GPIO_ODR)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        gpioa[0] = cmd          # set data on port A
        gpiob[1] = D_C | WR     # set C/D and WR low
        gpiob[0] = D_C | WR     # set C/D and WR high#
#
# Send a command and read data from the TFT controller
# cmd is the command byte, data must be a bytearray object for the returned data,
# int is the expected size of the data. data must match at least that size
#
    @staticmethod
    @micropython.viper        
    def tft_read_cmd_data(cmd: int, data: ptr8, size: int):
        gpioa = ptr8(stm.GPIOA)
        gpiob = ptr16(stm.GPIOB + stm.GPIO_BSRRL)
        gpioam = ptr16(stm.GPIOA + stm.GPIO_MODER)

        gpioa[stm.GPIO_ODR] = cmd  # set data on port A
        gpiob[1] = D_C | WR     # set C/D and WR low
        gpiob[0] = D_C | WR     # set C/D and WR high

        gpioam[0] = 0            # configure X1..X8 as Input

        for i in range(size):
            gpiob[1] = RD       # set RD low. C/D still high
            delay = 1           # short delay required
            data[i] = gpioa[stm.GPIO_IDR]  # get data from port A
            gpiob[0] = RD       # set RD high again

        gpioam[0] = 0x5555      # configure X1..X8 as Output
#
# Assembler version of send a command byte and read data from to the TFT controller
# data must be a bytearray object, int is the size of the data.
# The speed is about 130 ns/byte
#
    @staticmethod
    @micropython.asm_thumb
    def tft_read_cmd_data_AS(r0, r1, r2):  
# r0: command, r1: ptr to data buffer, r2 is expected size in bytes
# set up pointers to GPIO
# r5: bit mask for control lines
# r6: GPIOA base register ptr
# r7: GPIOB BSSRL register ptr
        movwt(r6, stm.GPIOA) # target
        movwt(r7, stm.GPIOB)
        add (r7, stm.GPIO_BSRRL)
# Emit command byte
        movw(r5, WR | D_C)
        strb(r0, [r6, stm.GPIO_ODR])  # set command byte
        strh(r5, [r7, 2])  # WR and D_C low
        strh(r5, [r7, 0])  # WR and D_C high
# now switch gpioaa to input
        movw(r0, 0)
        strh(r0, [r6, stm.GPIO_MODER])
# now loop though data
        movw(r5, RD)
        b(loopend)

        label(loopstart)
        strh(r5, [r7, 2])  # RD low
        nop()              # short delay
        nop()
        ldrb(r4, [r6, stm.GPIO_IDR])  # load data   
        strh(r5, [r7, 0])  # RD high
        strb(r4, [r1, 0])  # Store data
        add (r1, 1)  # advance data ptr

        label(loopend)
        sub (r2, 1)  # End of loop?
        bpl(loopstart)
# now switch gpioaa back to input
        movw(r0, 0x5555)
        strh(r0, [r6, stm.GPIO_MODER])
#
# swap byte pairs in a buffer
# sometimes needed for picture data
#
    @staticmethod
    @micropython.asm_thumb
    def swapbytes(r0, r1):               # bytearray, len(bytearray)
        mov(r2, 1)  # divide loop count by 2
        lsr(r1, r2) # to avoid odd valued counter
        b(loopend)

        label(loopstart)
        ldrb(r2, [r0, 0])
        ldrb(r3, [r0, 1])
        strb(r3, [r0, 0])
        strb(r2, [r0, 1])
        add(r0, 2)

        label(loopend)
        sub (r1, 1)  # End of loop?
        bpl(loopstart)

#
# swap colors red/blue in the buffer
#
    @staticmethod
    @micropython.asm_thumb
    def swapcolors(r0, r1):               # bytearray, len(bytearray)
        mov(r2, 3)
        udiv(r1, r1, r2)  # 3 bytes per triple
        b(loopend)

        label(loopstart)
        ldrb(r2, [r0, 0])
        ldrb(r3, [r0, 2])
        strb(r3, [r0, 0])
        strb(r2, [r0, 2])
        add(r0, 3)

        label(loopend)
        sub (r1, 1)  # End of loop?
        bpl(loopstart)

