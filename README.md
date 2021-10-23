# RISC OS Font control parsing in Python

This repository contains a class (`FontControlParser`) for parsing font control codes from a
byte squence, in Python.

It is part of the RISC OS Pyromaniac font system, and provides support for the SWIs which operate
on the font strings:

* `Font_Paint` - uses the controls to determine what should be rendered.
* `Font_ScanString` - uses the controls to determine the size or break points of a string.

And all the other calls which call on to `Font_ScanString`:

* `Font_StringWidth` - reads the width of a string.
* `Font_StringBBox` - reads the coverage of a string.
* `Font_FindCaret` - finds the position of the caret within a string.
* `Font_FindCaretJ` - a variant of the `Font_FindCaret` call.

The `FontContext` provides information which allows the operation of the following calls:

* `Font_CurrentFont` - reads the current font.
* `Font_FutureFont` - reads what the font would be after one of the sizing calls.
* `Font_CurrentRGB` - reads the current colour.
* `Font_FutureRGB` - reads what the colour would be after one of the sizing calls.


## Usage

Inside RISC OS Pyromaniac...

* The `FontControlParser` is subclassed to allow the memory access to occur within the
  emulated memory, not using the bytes.
* The `FontSpacing` is subclassed to create spacing from the memory blocks.
* The `FontContext` is subclassed to allow the GCOL/RGB operations, font lookups, sizing and rendering operations to be performed on the RISC OS graphics system.

A font context is created on initialisation, and will be updated by different operations:

```
self.context = FontContextPyromaniac(self.ro, self.fonts)
```

The font parser is constructed and supplied the memory buffers to parse:

```
memstring = self.ro.memory[regs[1]]
fc = FontControlParserPyromaniac(self.ro)
fc.debug_enable = self.debug_fontparser
fc.parse(memstring, string_length)
```

Once the other parameters for Font_Paint have been decoded and spacing and transformed written
to the `FontContext`, the paint operation is called.

```
self.context.x = xmilli
self.context.y = ymilli
self.context.transform = transform

with self.ro.kernel.graphics.vducursor.disable():
    self.context.paint(fc.sequence, spacing)

    # Update OS_ChangedBox
    x0 = int(self.context.bounds.x0 / riscos.graphics.font.FontConstants.Font_OSUnit) >> xeig
    y0 = int(self.context.bounds.y0 / riscos.graphics.font.FontConstants.Font_OSUnit) >> xeig
    x1 = int(self.context.bounds.x1 / riscos.graphics.font.FontConstants.Font_OSUnit) >> yeig
    y1 = int(self.context.bounds.y1 / riscos.graphics.font.FontConstants.Font_OSUnit) >> yeig
    self.ro.kernel.graphics.changedbox_update(x0, y0, x1, y1)
```

`Font_ScanString` is similar, but instead of operating on the current context, the future context is updated:

```
self.context.copy(to=self.future_context)
...
memstring = self.ro.memory[regs[1]]
fc = FontControlParserPyromaniac(self.ro)
fc.debug_enable = self.debug_fontparser
fc.parse(memstring, string_length)
...
(split_offset, splits) = self.future_context.size(fc.sequence, spacing=spacing, limits=(xmilli, ymilli),
                                                  split_char=split_char)
```

This allows all the `Font_Future*` calls to query the `self.future_context`

## Tests

Tests exist to show that the module is working properly, intended for use on GitLab.
Code coverage is reported as well.

To test, use:

```
make tests PYTHON=python2
```

Tests don't work on Python 3 yet, due to some problems with the processing of byte sequences.

To run coverage, use:

```
make coverage
```
