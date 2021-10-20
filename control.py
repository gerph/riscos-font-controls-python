"""
Font control sequences and the context they will update.

The FontControlParser object will parse the font control sequences as expected by
the RISC OS FontManager. These control sequences will be collected into a
FontControlSequence object, which is a list-like object which contains a number
of FontControl* objects. Each of these FontControl* objects is descended from the
FontControlBase, and includes references to the start and end indexes of the
font control string which was used to construct them.
"""

import struct

from riscos.graphics.structs import Bounds, Matrix


class FontBase(object):
    """
    A font object which holds information about the selected font.

    This is assigned to the FontControlParser.font_class to allow it to find the relevant
    font for a given font handle. It does not need to be an implementation of a Font,
    merely to hold the font handle information. However, implementations may choose to
    provide a richer interface if that aids the implementation of FontContext's state
    and rendering operations.
    """
    def __init__(self, ro, font_handle):
        self.ro = ro
        self.font_handle = font_handle


class FontSpacing(object):
    """
    Spacing defines how the words (space separated sequences) and characters are spaced out.
    """
    word_xoffset = 0
    word_yoffset = 0
    char_xoffset = 0
    char_yoffset = 0

    def __init__(self, word=None, char=None):
        """
        Track the spacing of words and characters

        @param word:    Spacing of words (at the space characters) as a tuple of (x, y)
        @param char:    Spacing of characters (between individual characters) as a tuple of (x, y)
        """
        if word:
            self.word_xoffset = word[0]
            self.word_yoffset = word[1]
        if char:
            self.char_xoffset = char[0]
            self.char_yoffset = char[1]

    def __repr__(self):
        return "<{}(word=+{}, char=+{})>".format(self.__class__.__name__,
                                                 (self.word_xoffset, self.word_yoffset),
                                                 (self.char_xoffset, self.char_yoffset))

    def __bool__(self):
        """
        Is anything set for the spacings?
        """
        return bool(self.word_xoffset != 0 or \
                    self.word_yoffset != 0 or \
                    self.char_xoffset != 0 or \
                    self.char_yoffset != 0)
    __nonzero__ = __bool__  # Python 2


class FontContext(object):
    """
    Information and interface to rendering the processed font string.

    The FontContext contains enough information to hold the current rendering state between
    operations. State updates are performed by the managing system, or by the FontControl parser
    objects. Rendering operations are performed by the FontControl parser system in their
    paint methods.

    FIXME: Parts of this code do not handle UTF-8, nor text in a non-horizontal direction.

    Managing systems should subclass this object and provide replacement functions for the
    methods which they can provide:

        gcol_to_rgb: Convert from the GCOL number given in the font control to an RGB colour
            value.
        rgb_to_gcol: Convert from an RGB colour value to a GCOL number.
        font_lookup: Convert from a RISC OS handle to a Font object, performing any necessary
            validation.
        font_bounds: Calculate the bounds of a given string for the current context.
        font_paint: Paint a given string using the current context.
        draw_underline: Draw an underline rectangle.

    The user of these objects may call methods to select state, and perform sizing and paint
    operations:

        copy: Create a new FontContext with the same settings as this one.
        clear_bounds: Clear the bounding box covered by the font operations to a null rectangle.
        clear_transform: Clear the transform to the identity matrix.
        select_font: Select a font by its handle.
        select_colour: Select colour parameters.
        paint: Paint a sequence from the FontControlParser using the context.
        size: Size a sequence from the FontControlParser using the context.
              FIXME: Not implemented.
    """
    font_class = FontBase
    debug_enable = False

    def __init__(self, ro):
        self.ro = ro

        # Maximum colour number (used for GCOL bounding)
        self.maxcol = 7

        # Colour range for SetFontColours
        self.bg = 0
        self.fgbase = 0
        self.fgoffset = 0

        # Logical colour numbers and palette values
        self.fg = 0
        self.fgpal = 0x00000010
        self.bgpal = 0x00000010

        # The current font we're using
        self.font_handle = 0
        self.font = None

        # Underline position and thickness
        self.underline_pos = 0
        self.underline_thickness = 0

        # Rendering matrix
        self.transform = Matrix(self.ro)

        # Rendering location
        self.x = 0
        self.y = 0

        # Bounds for sizing
        self.limitx = None
        self.limity = None

        # Current bounds
        self.bounds = Bounds(self.ro)

    def __repr__(self):
        return "<{}(x={}, y={}, font={}, bg={}, fg={}, bounds={})>".format(self.__class__.__name__,
                                                                           self.x, self.y,
                                                                           self.font,
                                                                           self.bg, self.fg,
                                                                           self.bounds)

    def clear_bounds(self):
        self.bounds = Bounds(self.ro)

    def clear_transform(self):
        self.transform = Matrix(self.ro)

    def clear_underline(self):
        self.underline_pos = 0
        self.underline_thickness = 0

    def copybase(self):
        return self.__class__(self.ro)

    def copy(self, to=None):
        if not to:
            to = self.copybase()

        to.maxcol = self.maxcol

        to.bg = self.bg
        to.fgbase = self.fgbase
        to.fgoffset = self.fgoffset

        to.fg = self.fg
        to.fgpal = self.fgpal
        to.bgpal = self.bgpal

        to.font_handle = self.font_handle
        to.font = self.font

        to.underline_pos = self.underline_pos
        to.underline_thickness = self.underline_thickness

        to.transform = self.transform

        to.x = self.x
        to.y = self.y

        to.limitx = self.limitx
        to.limity = self.limity

        to.bounds = self.bounds.copy()

        return to

    def debug(self, message):
        print(message)

    @staticmethod
    def saturate(value, vmin, vmax):
        """
        Limit a value to the given min and max
        """
        return max(min(value, vmax), vmin)

    def gcol_to_rgb(self, gcol):
        """
        Convert GCOL value to RGB.

        This stub assumes that you have a 1 bit of R, G and B.
        """
        r = (255<<8) if (gcol & 1) else 0
        g = (255<<16) if (gcol & 2) else 0
        b = (255<<24) if (gcol & 4) else 0
        return r | g | b | 0x10

    def rgb_to_gcol(self, rgb):
        """
        Convert RGB value to GCOL.

        This stub assumes that you have a 1 bit of R, G and B.
        """
        gcol = ((rgb>>15) & 1) | ((rgb>>22) & 2) | ((rgb>>29) & 4)
        return gcol

    def _gcol_updated(self):
        """
        GCOL values have updated; bound and set up RGB.
        """
        self.bg = self.saturate(self.bg, vmin=0, vmax=self.maxcol)
        self.fg = self.saturate(self.fg, vmin=0, vmax=self.maxcol)
        self.fgbase = self.saturate(self.fg - self.fgoffset, vmin=0, vmax=self.maxcol)
        self.fgoffset = self.fg - self.fgbase
        #print("gcol updated: bg=%i, fgbase=%i, fg=%i, fgoffset=%i" % (self.bg, self.fg, self.fgbase, self.fgoffset))

        self.fgpal = self.gcol_to_rgb(self.fg)
        self.bgpal = self.gcol_to_rgb(self.bg)

    def _rgb_updated(self):
        """
        Update the GCOL values for the RGB values that have been selected.
        """
        # Convert the colours to GCOL values
        self.bg = self.rgb_to_gcol(self.bgpal)
        self.fg = self.rgb_to_gcol(self.fgpal)
        self.fgbase = self.fg - self.fgoffset
        #print("rgb updated: bg=%i, fgbase=%i, fg=%i, fgoffset=%i" % (self.bg, self.fg, self.fgbase, self.fgoffset))

        # ... and then just update the GCOL colours to set everything right
        self._gcol_updated()

    def select_font(self, font_handle):
        """
        Select a RISC OS font handle as the current font.

        May raise exceptions if the font handle is invalid.
        """
        self.font = self.font_lookup(font_handle)
        self.font_handle = font_handle

    def select_colour(self, bg=None, fg=None, fgoffset=None, bgpal=None, fgpal=None):
        """
        Select colours for rendering.
        """
        gcol_changed = False
        rgb_changed = False
        #print("select_colour: bg=%r, fg=%r, fgoffset=%r, bgpal=%s, fgpal=%s" % (bg, fg, fgoffset, bgpal, fgpal))

        if fg is not None:
            self.fgbase = fg
            gcol_changed = True
        if bg is not None:
            self.bg = bg
            gcol_changed = True

        if fgoffset is not None:
            self.fgoffset = fgoffset

        if gcol_changed or fgoffset is not None:
            self.fg = self.fgbase + self.fgoffset

        if gcol_changed:
            # Cause the GCOLs to be converted to palette entries
            self._gcol_updated()

        if fgpal is not None:
            self.fgpal = fgpal
            rgb_changed = True
        if bgpal is not None:
            self.bgpal = bgpal
            rgb_changed = True

        if rgb_changed:
            # Cause the palette entries to be converted to GCOL colours
            #print("RGB : bg=&{:08x} fg=&{:08x}".format(bgpal, fgpal))
            self._rgb_updated()

    def font_lookup(self, font_handle):
        """
        Convert the font handle supplied into an object.

        This default implementation uses the font_class from this object to create the
        FontBase object which will be used for rendering.
        """
        return self.font_class(self.ro, font_handle)

    def font_paint(self, string):
        """
        Paint the font using the current context.

        @param string:      The string to process
        """

        # Note: Must apply the matrix, and the x,y offset
        pass

    def font_bounds(self, string):
        """
        Report the size of the supplied string or the font, applying the context.

        @param string:      The string to process, or None to read the font bounds.

        @return: tuple of (xleft, ybottom, xright, ytop, xoffset, yoffset) in millipoints
        """

        # FIXME: Should report the limit point as an index as well.

        # Note: Must apply the matrix.
        return (0, 0, 0, 0, 0, 0)

    def draw_underline(self, bounds):
        """
        Draw an underline bar for the text being rendered.

        @param bounds:      Region that the underline should be drawn as a pair of coordinates
        """
        pass

    def size(self, sequence, spacing=None, limits=None, split_char=None, continued=False):
        """
        Find the extent of the FontControlSequence.

        @return: (<terminating index>, <count of splits seen>)
        """

        # When performing sizing, we always base at 0, 0, and we want a clear bounding box
        if not continued:
            # But only when we're not using our special entry point to split by characters
            self.x = 0
            self.y = 0
            self.clear_bounds()
            self.clear_underline()

            self.limitx = 0x7FFFFFFF if limits is None else limits[0]
            self.limity = 0x7FFFFFFF if limits is None else limits[1]

        last_context = self.copy()
        last_split_point = self.copy()
        last_split_index = 0
        last_index = 0
        last_splits_seen = 0

        def beyond_limits(context):
            return ((context.limitx >= 0 and context.x > context.limitx) or
                    (context.limitx < 0 and context.x > context.limitx) or
                    (context.limity >= 0 and context.y > context.limity) or
                    (context.limity < 0 and context.y < context.limity))

        for ctrl in sequence.apply_spacing(self, spacing, split_char=split_char):
            self.copy(to=last_context)
            if self.debug_enable:
                self.debug("Applying %r to %r" % (ctrl, self))
            ctrl.apply(self)
            if self.debug_enable:
                self.debug("Now at %r " % (self,))

            splits_seen = 0
            string = ''
            if isinstance(ctrl, FontControlString):
                string = ctrl.string
                if split_char is None:
                    # FIXME: Not valid for UTF-8
                    splits_seen += len(string)
                else:
                    if ctrl.string == split_char or split_char == -1:
                        splits_seen = 1

            # FIXME: RTL rendering will need to reverse this check?
            if beyond_limits(self):
                # This sequence did not fit, so we must return the details from the last context
                if self.debug_enable:
                    self.debug("Did not fit, deciding what to report")
                if split_char and split_char != -1:
                    # If there was a split character, the context for the last split is found
                    if self.debug_enable:
                        self.debug("Returning the last split point")
                    last_split_point.copy(to=self)
                    return (last_split_index, last_splits_seen)
                else:
                    # No split character is set, so we may need to find the correct character
                    # to split at.
                    if self.debug_enable:
                        self.debug("Returning the last characters written, which was %r" % (last_context,))
                    if len(string) > 1:
                        # Need to find the right split character; the easiest way to do this is
                        # to call ourselves with this string split by character.
                        if self.debug_enable:
                            self.debug("Re-splitting this sequence, by characters")
                        sequence = FontControlSequence(self.ro)
                        sequence.append(ctrl)
                        (last_index, splits_seen) = last_context.size(sequence, split_char=-1, continued=True)
                        last_splits_seen += splits_seen

                last_context.copy(to=self)
                return (last_index, last_splits_seen)

            if splits_seen and split_char:
                # If this was a split point we passed, we remember this so we can return it.
                self.copy(to=last_split_point)
                last_split_index = ctrl.index_end

            last_index = ctrl.index_end
            last_splits_seen += splits_seen

        return (last_index, last_splits_seen)

    def paint(self, sequence, spacing):
        """
        Paint the FontControlSequence.
        """
        self.clear_bounds()
        self.clear_underline()

        if self.debug_enable:
            self.debug("Painting sequence: {!r}".format(sequence))
        for ctrl in sequence.apply_spacing(self, spacing):
            if self.debug_enable:
                self.debug("  Painting control: {!r}".format(ctrl))
            ctrl.paint(self)


class FontControlBase(object):
    """
    Base class for managing the control codes in font strings.

    All the FontControl* classes descend from this class.
    """

    def __init__(self, ro, indexes):
        self.ro = ro
        self.index_start = indexes[0]
        self.index_end = indexes[1]

    def properties(self):
        return ['No properties']

    def __repr__(self):
        return "<{}({}-{}, {})>".format(self.__class__.__name__,
                                        self.index_start, self.index_end,
                                        ', '.join(self.properties()))

    def apply(self, context):
        """
        Apply configuration changes for this control to the context.

        @param context:     FontContext to use to get information, updated with changed paramters
        """
        (xleft, ybottom, xright, ytop, xoffset, yoffset) = self.size(context)

        context.bounds += (context.x + xleft, context.y + ybottom,
                           context.x + xright, context.y + ytop)

        # To apply the matrix we should transform the bottom right coord.
        context.x += xoffset
        context.y += yoffset

        return (xleft, ybottom, xright, ytop, xoffset, yoffset)

    def size(self, context):
        """
        Perform a sizing on the context supplied.

        @param context:     FontContext to use to get information, updated with new parameters
        @return: tuple of (xleft, ybottom, xright, ytop, xoffset, yoffset)
        """

        return (0, 0, 0, 0, 0, 0)

    def paint(self, context):
        """
        Paint any necessary content, using the supplied context.

        @param context:     FontContext to paint with, updated with new position

        @return: tuple of (xoffset, yoffset) in millipoints
        """
        self.apply(context)

        return (0, 0)


class FontControlUnderlineMixin(object):

    def underline(self, context):
        (xleft, ybottom, xright, ytop, xoffset, yoffset) = self.size(context)

        # Render the underline before the font
        if context.underline_thickness:
            underline = Bounds(context.ro,
                               x0=context.x, y0=context.y + context.underline_pos - context.underline_thickness,
                               x1=context.x + xoffset, y1=context.y + context.underline_pos)
            # FIXME: This isn't right if the font is at an angle; for now it suffices as the fonts will
            #        largely be rendered left-to-right, with no y-offset caused by the font matrix.
            context.draw_underline(underline)

            context.bounds += underline


class FontControlString(FontControlBase, FontControlUnderlineMixin):
    """
    A renderable string.
    """

    def __init__(self, ro, indexes, string):
        super(FontControlString, self).__init__(ro, indexes)
        self.string = string

    def properties(self):
        return ['string={!r}'.format(self.string)]

    def size(self, context):
        self.string = bytes(self.string)
        (xleft, ybottom, xright, ytop, xoffset, yoffset) = context.font_bounds(self.string)

        # Bounds should be have the matrix applied to it.
        if context.transform:
            #print("Applying matrix %r to %r" % (context.transform, (xleft, ybottom, xright, ytop)))
            (xleft, ybottom, xright, ytop) = context.transform.bbox(xleft, ybottom, xright, ytop)
            #print("  => %r" % ((xleft, ybottom, xright, ytop),))

            # The position we base out plotting at should not be offset by the offset position (ie if the font
            # is plotted x+10, we don't increase our x position by 10 every call.
            (xoffset, yoffset) = context.transform.apply(xoffset, yoffset)

        return (xleft, ybottom, xright, ytop, xoffset, yoffset)

    def paint(self, context):
        (xleft, ybottom, xright, ytop, xoffset, yoffset) = self.size(context)

        self.underline(context)

        context.font_paint(self.string)

        super(FontControlString, self).paint(context)

        return (xoffset, yoffset)


class FontControlMove(FontControlBase):
    """
    A move operation (control codes 9 and 11).
    """

    def __init__(self, ro, indexes, dx=0, dy=0):
        super(FontControlMove, self).__init__(ro, indexes)
        self.dx = dx
        self.dy = dy

    def properties(self):
        p = []
        if self.dx:
            p.append('dx={}'.format(self.dx))
        if self.dy:
            p.append('dy={}'.format(self.dy))
        if not p:
            p.append('<no move>')
        return p

    def size(self, context):
        return (0, 0, 0, 0, self.dx, self.dy)


class FontControlMatrix(FontControlBase):
    """
    A change of the matrix to use for rendering (control code 27 or 28).
    """

    def __init__(self, ro, indexes, matrix):
        super(FontControlMatrix, self).__init__(ro, indexes)
        self.matrix = matrix

    def properties(self):
        return ['matrix={}'.format(self.matrix)]

    def apply(self, context):
        # Note: The matrix *replaces* the existing matrix (it does not get applied
        #       to the existing matrix).
        context.transform = self.matrix
        return super(FontControlMatrix, self).apply(context)


class FontControlGCOL(FontControlBase):
    """
    A change of the GCOL colours used for rendering (control code 17 or 18).
    """

    def __init__(self, ro, indexes, fg=None, bg=None, offset=None):
        super(FontControlGCOL, self).__init__(ro, indexes)
        self.fg = fg
        self.bg = bg
        self.offset = None

    def properties(self):
        p = []
        if self.bg is not None:
            p.append('bg={}'.format(self.bg))
        if self.fg is not None:
            p.append('fg={}'.format(self.fg))
        if self.offset is not None:
            p.append('offset={}'.format(self.offset))
        return p

    def apply(self, context):
        context.select_colour(fg=self.fg, bg=self.bg, fgoffset=self.offset)
        return super(FontControlGCOL, self).apply(context)


class FontControlRGB(FontControlBase):
    """
    A change of the RGB colours used for rendering (control code 19).
    """

    def __init__(self, ro, indexes, fg=None, bg=None, offset=None):
        super(FontControlRGB, self).__init__(ro, indexes)
        self.fg = fg
        self.bg = bg
        self.offset = None

    def properties(self):
        p = []
        if self.bg is not None:
            p.append('bg=&{:08x}'.format(self.bg))
        if self.fg is not None:
            p.append('fg=&{:08x}'.format(self.fg))
        if self.offset is not None:
            p.append('offset={}'.format(self.offset))
        return p

    def apply(self, context):
        context.select_colour(fgpal=self.fg, bgpal=self.bg, fgoffset=self.offset)
        return super(FontControlRGB, self).apply(context)


class FontControlComment(FontControlBase):
    """
    An inline comment (control code 21).
    """

    def __init__(self, ro, indexes, comment):
        super(FontControlComment, self).__init__(ro, indexes)
        self.comment = comment

    def properties(self):
        return ['comment={!r}'.format(self.comment)]


class FontControlUnderline(FontControlBase):
    """
    An underline change (control code 25).
    """

    def __init__(self, ro, indexes, pos, thickness):
        super(FontControlUnderline, self).__init__(ro, indexes)
        self.underline_pos = pos
        self.underline_thickness = thickness

    def properties(self):
        if self.underline_thickness:
            return ['underline at {}, thickness {}'.format(self.underline_pos, self.underline_thickness)]
        return ['Disable underline']

    def apply(self, context):
        # Get the size of the font.
        (x0, y0, x1, y1, xoffset, yoffset) = context.font_bounds(None)
        multiplier = y1 / 256.0
        context.underline_pos = self.underline_pos * multiplier
        context.underline_thickness = self.underline_thickness * multiplier

        return super(FontControlUnderline, self).apply(context)


class FontControlFont(FontControlBase):
    """
    An font change (control code 26).
    """

    def __init__(self, ro, indexes, font_handle):
        super(FontControlFont, self).__init__(ro, indexes)
        self.font_handle = font_handle

    def properties(self):
        return ['font_handle={}'.format(self.font_handle)]

    def apply(self, context):
        context.select_font(self.font_handle)
        return super(FontControlFont, self).apply(context)


class FontControlMoveCharacter(FontControlMove, FontControlUnderlineMixin):

    def paint(self, context):
        self.underline(context)
        return super(FontControlMoveCharacter, self).paint(context)


class FontControlMoveSpace(FontControlMove, FontControlUnderlineMixin):

    def paint(self, context):
        self.underline(context)
        return super(FontControlMoveSpace, self).paint(context)


class FontControlSequence(object):
    """
    Object which holds the sequence of FontControl operations.
    """

    def __init__(self, ro):
        self.ro = ro
        self.sequence = []

    def __repr__(self):
        return "<{}({} items)>".format(self.__class__.__name__,
                                       len(self.sequence))

    def __iter__(self):
        return iter(self.sequence)

    def __len__(self):
        return len(self.sequence)

    def __getitem__(self, index):
        return self.sequence[index]

    def append(self, fc):
        self.sequence.append(fc)

    def _apply_splits(self, sequence, split_char=None):
        """
        Split up the strings into sections when we encounter a given split character.
        """
        for ctrl in sequence:
            if isinstance(ctrl, FontControlString) and split_char:
                s = bytes(ctrl.string)
                if split_char == -1:
                    parts = [b for b in s]
                else:
                    parts = s.split(split_char)

                if len(parts) == 1:
                    yield ctrl
                else:
                    offset = 0
                    for part, s in enumerate(parts):
                        if isinstance(s, int):
                            s = bytes(bytearray([s]))
                        last = (part == len(parts) - 1)

                        size = len(s)
                        indexes = (ctrl.index_start + offset, ctrl.index_start + offset + size)
                        if s:
                            yield FontControlString(self.ro, indexes, s)
                        offset += size
                        if not last and split_char != -1:
                            indexes = (ctrl.index_start + offset, ctrl.index_start + offset + 1)
                            yield FontControlString(self.ro, indexes, split_char)
                            offset += 1
            else:
                yield ctrl

    def apply_spacing(self, context, spacing, split_char=None):
        """
        Create a new sequence of operations which introduces spacing.

        @param context:     The font rendering context
        @param spacing:     The spacing to apply to the strings
        @param split_char:  Character to split on, or None to not split the strings on a character,
                            or -1 to split on every character

        Generates a sequence of the controls which contain extra move operations for the requested
        spacing.
        """
        for ctrl in self._apply_splits(self.sequence, split_char):
            # The strings only get expanded if there is a spacing
            if isinstance(ctrl, FontControlString) and spacing:
                # We do the splits slightly differently depending on whether we have character
                # offsets present or not.

                # FIXME: We should decode the string prior to splitting? Consider the UTF-8
                #        strings.
                s = bytes(ctrl.string)
                word_split = False
                if spacing.char_xoffset or spacing.char_yoffset:
                    # We want to split into character offsets
                    parts = [b for b in s]
                else:
                    # We want to split into words
                    # FIXME: Decide if this really should be splits on spaces, or splits on
                    #        whitespace property?
                    parts = s.split(b' ')
                    word_split = True

                offset = 0
                for part, s in enumerate(parts):
                    if isinstance(s, int):
                        s = bytes(bytearray([s]))
                    last = (part == len(parts) - 1)
                    if word_split and not last:
                        s += b' '
                    if not s:
                        continue

                    size = len(s)
                    indexes = (ctrl.index_start + offset, ctrl.index_start + offset + size)
                    yield FontControlString(self.ro, indexes, s)
                    if not word_split:
                        yield FontControlMoveCharacter(self.ro, (indexes[1], indexes[1]),
                                                       dx=spacing.char_xoffset, dy=spacing.char_yoffset)
                        if s == b' ' and (spacing.word_xoffset or spacing.word_yoffset):
                            yield FontControlMoveSpace(self.ro, (indexes[1], indexes[1]),
                                                       dx=spacing.word_xoffset, dy=spacing.word_yoffset)
                    else:
                        if s[-1] == b' ':
                            yield FontControlMoveSpace(self.ro, (indexes[1], indexes[1]),
                                                       dx=spacing.word_xoffset, dy=spacing.word_yoffset)
                    offset += size

            else:
                yield ctrl


class FontControlParser(object):
    """
    Parser structure for font control strings.

    The FontControlParser is expected to be overridden with a dedicated properties and
    methods to handle the implementation:

        read_byte, read_signedword, read_word should be replaced with a method which read from
            the string, returning integer values and incrementing the string index.
        read_matrix should be replaced with a method which reads a matrix from the string,
            returning an object suitable for performing transformations.
    """
    font_class = FontBase

    def __init__(self, ro):
        self.ro = ro
        self.sequence = FontControlSequence(ro)
        self.string = bytearray(b'')
        self.index = 0
        self.max_length = 0

        # Whether we're debugging
        self.debug_enable = False

    def clear(self):
        """
        Clear all state (sequence and parser)
        """
        self.sequence = FontControlSequence(self.ro)
        self.reset()

    def reset(self):
        """
        Reset the parser, but keep the current sequence.
        """
        self.string = bytearray(b'')
        self.index = 0
        self.max_length = 0

    def debug(self, message):
        print(message)

    def step_back(self):
        """
        Move back byte.
        """
        if self.index:
            self.index -= 1

    def read_byte(self):
        """
        Read a single byte from our input string.

        @return: unsigned byte value
        """
        if self.index >= len(self.string) or \
           self.index >= self.max_length:
            # End of string, so we return terminator
            self.index += 1
            return 0
        b = self.string[self.index]
        self.index += 1
        return b

    def read_signedword(self):
        """
        Read a signed word (4 bytes, little endian) from our input string.

        @return: 32bit signed value from string, or None if invalid
        """
        return self.read_word(signed=True)

    def read_word(self, signed=False):
        """
        Read an unsigned/signed word (4 bytes, little endian) from our input string.

        @return: 32bit unsigned/signed value from string, or None if invalid
        """
        if self.index + 3 > len(self.string) or \
           self.index + 3 > self.max_length:
            # End of string, so we return as invalid
            return None
        data = self.string[self.index:self.index + 4]
        if signed:
            (value,) = struct.unpack('<l', data)
        else:
            (value,) = struct.unpack('<L', data)
        self.index += 4
        return value

    def read_matrix(self, with_translation=False):
        """
        Read a matrix of 4 or 6 words.

        @return: tuple of 6 values
        """
        (a, b) = (self.read_signedword(), self.read_signedword())
        (c, d) = (self.read_signedword(), self.read_signedword())
        if with_translation:
            (e, f) = (self.read_signedword(), self.read_signedword())
        else:
            e = 0
            f = 0
        return Matrix(None,
                      array=(a / 65536.0, b / 65536.0,
                             c / 65536.0, d / 65536.0,
                             e, f))

    def align(self):
        """
        Align to a word boundary.
        """
        self.index = (self.index + 3) & ~3

    def parse(self, string, max_length=None):
        """
        Parse the string to give us a sequence of FontControl* objects.
        """
        if max_length is None or max_length >= (1<<20) or max_length < 0:
            max_length = (1<<20)

        # Initialise ourselves for reading
        self.string = string
        self.max_length = max_length
        self.index = 0

        # Accumulate a stream of the different control codes
        while True:
            start_index = self.index
            b = self.read_byte()
            if b in (0, 10, 13):
                # Terminator
                # Move back so that we point to the terminator
                self.step_back()
                break

            elif b in (9, 11):
                # Move position (x, y)
                pos = self.read_byte() | (self.read_byte() << 8) | (self.read_byte() << 16)
                if self.debug_enable:
                    self.debug("FontParser: Delta {} {}".format('X' if b == 9 else 'Y', pos))
                if b == 9:
                    fc = FontControlMove(self.ro, (start_index, self.index),
                                         dx=pos)
                else:
                    fc = FontControlMove(self.ro, (start_index, self.index),
                                         dy=pos)
                self.sequence.append(fc)

            elif b == 17:
                # Change FG colour to GCOL colour
                gcol = self.read_byte()
                is_bg = gcol & 0x80
                gcol = gcol & 0x7f
                if self.debug_enable:
                    self.debug("FontParser: GCOL {}={}".format('bg' if is_bg else 'fg', gcol))
                if is_bg:
                    fc = FontControlGCOL(self.ro, (start_index, self.index),
                                         bg=gcol)
                else:
                    fc = FontControlGCOL(self.ro, (start_index, self.index),
                                         fg=gcol)
                self.sequence.append(fc)

            elif b == 18:
                # Change BG+FG colour to GCOL colour (bg, fg, offset)
                bg = self.read_byte()
                fg = self.read_byte()
                offset = self.read_byte()
                if self.debug_enable:
                    self.debug("FontParser: GCOL bg={}, fg={}".format(bg, fg))

                fc = FontControlGCOL(self.ro, (start_index, self.index),
                                     bg=bg, fg=fg, offset=offset)
                self.sequence.append(fc)

            elif b == 19:
                # Change BG+FG colour to RGB (r,g,b,R,G,B,offset)
                bg = (self.read_byte() << 8) | (self.read_byte() << 16) | (self.read_byte() << 24) | 0x10
                fg = (self.read_byte() << 8) | (self.read_byte() << 16) | (self.read_byte() << 24) | 0x10
                offset = self.read_byte()
                if self.debug_enable:
                    self.debug("FontParser: RGB bg=&{:08x}, fg=&{:08x}".format(bg, fg))
                fc = FontControlRGB(self.ro, (start_index, self.index),
                                    bg=bg, fg=fg, offset=offset)
                self.sequence.append(fc)

            elif b == 21:
                # Hidden comment string
                comment = bytearray()
                while True:
                    b = self.read_byte()
                    if b < 32:
                        break
                    comment.append(b)
                if self.debug_enable:
                    self.debug("FontParser: comment={!r}".format(comment))
                fc = FontControlComment(self.ro, (start_index, self.index),
                                        comment=comment)
                self.sequence.append(fc)

            elif b == 25:
                # Underline position and thickness
                pos = self.read_byte()
                thickness = self.read_byte()
                if pos > 127:
                    pos = pos - 256
                if self.debug_enable:
                    self.debug("FontParser: Underline position={}, thickness={}".format(pos, thickness))
                fc = FontControlUnderline(self.ro, (start_index, self.index),
                                          pos=pos, thickness=thickness)
                self.sequence.append(fc)

            elif b == 26:
                # Font handle
                font_handle = self.read_byte()
                if self.debug_enable:
                    self.debug("FontParser: Font {}".format(font_handle))
                fc = FontControlFont(self.ro, (start_index, self.index),
                                     font_handle=font_handle)
                self.sequence.append(fc)

            elif b == 27 or b == 28:
                # Change transform
                self.align()
                matrix = self.read_matrix(with_translation=(b != 27))
                if self.debug_enable:
                    self.debug("FontParser: Transform {}".format(matrix))
                fc = FontControlMatrix(self.ro, (start_index, self.index),
                                       matrix=matrix)
                self.sequence.append(fc)

            elif b < 32:
                # Some other control character; skip it?
                # FIXME: Should we skip or should we abort?
                break

            else:
                if len(self.sequence) and isinstance(self.sequence[-1], FontControlString):
                    last_string = self.sequence[-1]
                    # This is another character for the font string, so we need to accumulate it.
                    last_string.string.append(b)
                    # And update the end index
                    last_string.index_end = self.index
                else:
                    # We need to create a new string object
                    fc = FontControlString(self.ro, (start_index, self.index), bytearray([b]))
                    self.sequence.append(fc)

    def simple_string(self):
        """
        Return just the string content of this font control sequence was.
        """
        acc = bytearray()
        for fc in self.sequence:
            if isinstance(fc, FontControlString):
                acc.extend(fc.string)
        return bytes(acc)

    def nskipped_controls(self):
        """
        How many bytes were skipped out of this sequence
        """
        return self.index - len(self.simple_string())
