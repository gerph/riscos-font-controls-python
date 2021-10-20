#!/usr/bin/env python
"""
Test that the font control sequence processing works the way we expect.

SUT:    Ancilliary: Font
Area:   Control sequence parsing
Class:  Functional
Type:   Unit test
"""

import os
import sys
import unittest

try:
    import nose
except ImportError:
    nose = None

sys.path.append(os.path.join(os.path.dirname(__file__), 'riscos/pymods/fontmanager'))

import control


class FakeRISCOS(object):

    def __init__(self):
        self.fonts = {
                1: ['Homerton', 8, 16],
                2: ['Trinity', 32, 32],
                3: ['Corpus', 8, 8],
            }


class FontFake(control.FontBase):

    def __init__(self, ro, font_handle):
        super(FontFake, self).__init__(ro, font_handle)
        self.name = self.ro.fonts[font_handle][0]
        self.xsize = self.ro.fonts[font_handle][1]
        self.ysize = self.ro.fonts[font_handle][2]

    def bounds(self, context, string):
        """
        Report the size of the supplied string, applying the context.

        @param context:     The FontContext to use for the operations
        @param string:      The string to process

        @return: tuple of (xleft, ybottom, xright, ytop, xoffset, yoffset) in millipoints
        """

        if string is None:
            # Font character size
            return (0, 0, self.xsize, self.ysize, self.xsize, 0)

        # FIXME: Should apply matrix?
        return (0, 0,
                len(string) * self.xsize, self.ysize,
                len(string) * self.xsize, 0)

    def paint(self, context, string):
        """
        Paint the font using the context supplied.

        @param context:     The FontContext to use for the operations
        @param string:      The string to process
        """

        pass


class FontContextFake(control.FontContext):
    font_class = FontFake
    debug_enable = True

    def __init__(self, ro):
        super(FontContextFake, self).__init__(ro)
        self.paint_ops = []

    def font_bounds(self, string):
        return self.font.bounds(self, string)

    def font_paint(self, string):
        # Add the painted string to the buffer
        self.paint_ops.append((string, self.font.name, self.x, self.y, self.bg, self.fg))
        return self.font.paint(self, string)

    def draw_underline(self, bounds):
        self.paint_ops.append((None, bounds, self.fg))


class FCTestCase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        ro = FakeRISCOS()
        self.fc = FontContextFake(ro)
        self.fcp = control.FontControlParser(ro)

    def assertLen(self, size, op):
        self.assertEqual(size, len(op))

    def assertSequenceTypes(self, types):
        self.assertEqual(types, [type(x) for x in self.fcp.sequence])


class Test10BasicStrings(FCTestCase):

    def test_01_empty(self):
        self.fcp.parse(bytearray(b''))
        self.assertLen(0, self.fcp.sequence)
        self.assertEqual(0, self.fcp.index)

    def test_02_simple_string(self):
        self.fcp.parse(bytearray(b'hello world'))
        self.assertLen(1, self.fcp.sequence)
        self.assertEqual(11, self.fcp.index)

    def test_03_terminated_string(self):
        self.fcp.parse(bytearray(b'hello world\x0a'))
        self.assertLen(1, self.fcp.sequence)
        self.assertEqual(11, self.fcp.index)

    def test_10_zero_length(self):
        self.fcp.parse(bytearray(b'hello world\x0a'), 0)
        self.assertLen(0, self.fcp.sequence)
        self.assertEqual(0, self.fcp.index)

    def test_11_length_1(self):
        self.fcp.parse(bytearray(b'hello world\x0a'), 1)
        self.assertLen(1, self.fcp.sequence)
        self.assertEqual(1, self.fcp.index)

    def test_12_length_2(self):
        self.fcp.parse(bytearray(b'hello world\x0a'), 2)
        self.assertLen(1, self.fcp.sequence)
        self.assertEqual(2, self.fcp.index)


class Test20Controls(FCTestCase):

    def test_01_select_font(self):
        self.fcp.parse(bytearray(b'\x1a\x01font 1\x1a\x02font 2'))
        self.assertLen(4, self.fcp.sequence)
        self.assertEqual(16, self.fcp.index)
        self.assertSequenceTypes([control.FontControlFont,
                                  control.FontControlString,
                                  control.FontControlFont,
                                  control.FontControlString])

    def test_02_underline(self):
        self.fcp.parse(bytearray(b'\x19\xf0\x20underlined\x19\x00\x00off'))
        self.assertLen(4, self.fcp.sequence)
        self.assertEqual(19, self.fcp.index)
        self.assertSequenceTypes([control.FontControlUnderline,
                                  control.FontControlString,
                                  control.FontControlUnderline,
                                  control.FontControlString])

    def test_03_rgb(self):
        self.fcp.parse(bytearray(b'\x13\x00\x00\x00\xff\x00\x00\x00Red\x13\x00\x00\x00\xff\xff\xff\x00'))
        self.assertLen(3, self.fcp.sequence)
        self.assertEqual(19, self.fcp.index)
        self.assertSequenceTypes([control.FontControlRGB,
                                  control.FontControlString,
                                  control.FontControlRGB])

    def test_04_move(self):
        self.fcp.parse(bytearray(b'Move\x09\x80\x02\x00X\x0b\x00\x03\x00Y'))
        self.assertLen(5, self.fcp.sequence)
        self.assertEqual(14, self.fcp.index)
        self.assertSequenceTypes([control.FontControlString,
                                  control.FontControlMove,
                                  control.FontControlString,
                                  control.FontControlMove,
                                  control.FontControlString])

    def test_05_matrix(self):
        self.fcp.parse(bytearray(b'\x1b \x00\x00\x01\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00\x00\x01\x00Matrix'))
        self.assertLen(2, self.fcp.sequence)
        self.assertEqual(24, self.fcp.index)
        self.assertSequenceTypes([control.FontControlMatrix,
                                  control.FontControlString])


class Test30Painting(FCTestCase):

    def test_10_paint_plain(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'plain string'))
        for ctrl in self.fcp.sequence:
            ctrl.paint(self.fc)
        self.assertEqual(12 * 8, self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual([(b'plain string', 'Homerton', 0, 0,
                           0, 7)],
                         self.fc.paint_ops)

    def test_11_paint_plain_spacing_word(self):
        spacing = control.FontSpacing(word=(2, 0))
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'plain string'))
        for ctrl in self.fcp.sequence.apply_spacing(self.fc, spacing):
            print("context = %r, ctrl = %r" % (self.fc, ctrl))
            ctrl.paint(self.fc)
        self.assertEqual((12 * 8) + 2, self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual([(b'plain ', 'Homerton', 0, 0,
                           0, 7),
                          (b'string', 'Homerton', (6 * 8) + 2, 0,
                           0, 7)],
                         self.fc.paint_ops)

    def test_12_paint_plain_spacing_char(self):
        spacing = control.FontSpacing(char=(2, 0))
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'plain string'))
        for ctrl in self.fcp.sequence.apply_spacing(self.fc, spacing):
            ctrl.paint(self.fc)
        self.assertEqual((12 * 8) + (12 * 2), self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual([(b'p', 'Homerton', 0, 0,
                           0, 7),
                          (b'l', 'Homerton', 10, 0,
                           0, 7),
                          (b'a', 'Homerton', 20, 0,
                           0, 7),
                          (b'i', 'Homerton', 30, 0,
                           0, 7),
                          (b'n', 'Homerton', 40, 0,
                           0, 7),
                          (b' ', 'Homerton', 50, 0,
                           0, 7),
                          (b's', 'Homerton', 60, 0,
                           0, 7),
                          (b't', 'Homerton', 70, 0,
                           0, 7),
                          (b'r', 'Homerton', 80, 0,
                           0, 7),
                          (b'i', 'Homerton', 90, 0,
                           0, 7),
                          (b'n', 'Homerton', 100, 0,
                           0, 7),
                          (b'g', 'Homerton', 110, 0,
                           0, 7),
                         ],
                         self.fc.paint_ops)

    def test_13_paint_plain_spacing_word_char(self):
        spacing = control.FontSpacing(word=(5, 0), char=(2, 0))
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'plain string'))
        for ctrl in self.fcp.sequence.apply_spacing(self.fc, spacing):
            ctrl.paint(self.fc)
        self.assertEqual((12 * 8) + 5 + (12 * 2), self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual([(b'p', 'Homerton', 0, 0,
                           0, 7),
                          (b'l', 'Homerton', 10, 0,
                           0, 7),
                          (b'a', 'Homerton', 20, 0,
                           0, 7),
                          (b'i', 'Homerton', 30, 0,
                           0, 7),
                          (b'n', 'Homerton', 40, 0,
                           0, 7),
                          (b' ', 'Homerton', 50, 0,
                           0, 7),
                          (b's', 'Homerton', 65, 0,
                           0, 7),
                          (b't', 'Homerton', 75, 0,
                           0, 7),
                          (b'r', 'Homerton', 85, 0,
                           0, 7),
                          (b'i', 'Homerton', 95, 0,
                           0, 7),
                          (b'n', 'Homerton', 105, 0,
                           0, 7),
                          (b'g', 'Homerton', 115, 0,
                           0, 7),
                          ],
                          self.fc.paint_ops)

    def test_20_paint_change_font(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'one\x1a\x02two'))
        for ctrl in self.fcp.sequence:
            ctrl.paint(self.fc)
        self.assertEqual((3 * 8) + (3 * 32), self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual([(b'one', 'Homerton',
                           0, 0,
                           0, 7),
                          (b'two', 'Trinity',
                           (3 * 8), 0,
                           0, 7)],
                         self.fc.paint_ops)

    def test_30_paint_move(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'Move\x09\x80\x02\x00X\x0b\x00\x03\x00Y'))
        for ctrl in self.fcp.sequence:
            print("context = %r, ctrl = %r" % (self.fc, ctrl))
            ctrl.paint(self.fc)
        self.assertEqual([(b'Move', 'Homerton',
                           0, 0,
                           0, 7),
                          (b'X', 'Homerton',
                           (4 * 8) + 0x280, 0,
                           0, 7),
                          (b'Y', 'Homerton',
                           (4 * 8) + 0x280 + (1 * 8), 0x300,
                           0, 7)],
                         self.fc.paint_ops)
        self.assertEqual((4 * 8) + 0x280 + (1 * 8) + (1 * 8), self.fc.x)
        self.assertEqual(0x300, self.fc.y)
        self.assertEqual((0, 0, (4 * 8) + 0x280 + (1 * 8) + (1 * 8), 0x300 + 16),
                         self.fc.bounds)

    def test_40_paint_matrix_italic(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        # Italic 25%
        self.fcp.parse(bytearray(b'\x1b   \x00\x00\x01\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00\x00\x01\x00Font'))
        for ctrl in self.fcp.sequence:
            print("context = %r, ctrl = %r" % (self.fc, ctrl))
            ctrl.paint(self.fc)
        import pprint
        pprint.pprint(self.fc.paint_ops)
        self.assertEqual([(b'Font', 'Homerton',
                           0, 0,
                           0, 7)],
                         self.fc.paint_ops)
        self.assertEqual((4 * 8), self.fc.x)
        self.assertEqual(0x0, self.fc.y)
        self.assertEqual((0, 0, (4 * 8) + (16 * 0.25), 16), self.fc.bounds)

    def test_41_paint_matrix_sized(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        # Double width
        self.fcp.parse(bytearray(b'\x1b   \x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00Font'))
        for ctrl in self.fcp.sequence:
            print("context = %r, ctrl = %r" % (self.fc, ctrl))
            ctrl.paint(self.fc)
        import pprint
        pprint.pprint(self.fc.paint_ops)
        self.assertEqual([(b'Font', 'Homerton',
                           0, 0,
                           0, 7)],
                         self.fc.paint_ops,)
        self.assertEqual((4 * 8 * 2), self.fc.x)
        self.assertEqual(0x0, self.fc.y)
        self.assertEqual((0, 0, (4 * 8 * 2), 16),
                         self.fc.bounds)

    def test_50_paint_underline(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'\x19\xf0\x20underlined\x19\x00\x00off'))

        for ctrl in self.fcp.sequence:
            print("context = %r, ctrl = %r" % (self.fc, ctrl))
            ctrl.paint(self.fc)

        import pprint
        pprint.pprint(self.fc.paint_ops)
        self.assertEqual([(None, (0, -3, (10 * 8), -1), 7),     # The underline box
                          (b'underlined', 'Homerton',
                           0, 0,
                           0, 7),
                          (b'off', 'Homerton',
                           (10 * 8), 0,
                           0, 7)],
                          self.fc.paint_ops)
        self.assertEqual((10 * 8) + (3 * 8), self.fc.x)
        self.assertEqual(0x0, self.fc.y)
        self.assertEqual((0, -3, (10 * 8) + (3 * 8), 16),
                         self.fc.bounds)

    def test_51_paint_underline_spacing_word(self):
        spacing = control.FontSpacing(word=(5, 0))
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'\x19\xf0\x20underlined and\x19\x00\x00off'))

        for ctrl in self.fcp.sequence.apply_spacing(self.fc, spacing):
            ctrl.paint(self.fc)

        import pprint
        pprint.pprint(self.fc.paint_ops)
        self.assertEqual([(None, (0, -3, (11 * 8), -1), 7),     # The underline box
                          (b'underlined ', 'Homerton',
                           0, 0,
                           0, 7),
                          (None, ((11 * 8), -3, (11 * 8) + 5, -1), 7),          # The underline for word spacing
                          (None, ((11 * 8) + 5, -3, (14 * 8) + 5, -1), 7),      # The underline for 'and'
                          (b'and', 'Homerton',
                           (11 * 8) + 5, 0,
                           0, 7),
                          (b'off', 'Homerton',
                           (14 * 8) + 5, 0,
                           0, 7)],
                          self.fc.paint_ops)
        self.assertEqual((14 * 8) + 5 + (3 * 8), self.fc.x)
        self.assertEqual(0x0, self.fc.y)
        self.assertEqual((0, -3, (14 * 8) + 5 + (3 * 8), 16),
                         self.fc.bounds)


class Test40Sizing(FCTestCase):

    def test_10_size_plain(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'plain string'))

        (end_index, splits) = self.fc.size(self.fcp.sequence, spacing=None)

        self.assertEqual(12 * 8, self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual(12, end_index)
        self.assertEqual(12, splits)
        self.assertEqual((0, 0, (12 * 8), 16),
                         self.fc.bounds)

    def test_11_size_plain_spacing(self):
        spacing = control.FontSpacing(word=(5, 0))
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'plain string'))

        (end_index, splits) = self.fc.size(self.fcp.sequence, spacing=spacing, split_char=b' ')

        self.assertEqual((12 * 8) + 5, self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual(12, end_index)
        self.assertEqual(1, splits)
        self.assertEqual((0, 0, (12 * 8) + 5, 16),
                         self.fc.bounds)

    def test_12_size_plain_splits(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'plain string'))

        (end_index, splits) = self.fc.size(self.fcp.sequence, spacing=None, split_char=b' ')

        self.assertEqual(12 * 8, self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual(12, end_index)
        self.assertEqual(1, splits)
        self.assertEqual((0, 0, (12 * 8), 16),
                         self.fc.bounds)

    def test_13_size_plain_splits_limits(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'words. lots of words.'))

        (end_index, splits) = self.fc.size(self.fcp.sequence, spacing=None, limits=(8 * 8, 0), split_char=b' ')

        self.assertEqual(7 * 8, self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual(7, end_index)
        self.assertEqual(1, splits)
        self.assertEqual((0, 0, (7 * 8), 16),
                         self.fc.bounds)

    def test_14_size_plain_limits(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'words. lots of words.'))

        (end_index, splits) = self.fc.size(self.fcp.sequence, spacing=None, limits=(8 * 8, 0))

        self.assertEqual(8 * 8, self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual(8, end_index)
        self.assertEqual(8, splits)
        self.assertEqual((0, 0, (8 * 8), 16),
                         self.fc.bounds)

    def test_20_size_change_font(self):
        self.fc.select_font(1)
        self.fc.select_colour(bg=0, fg=7)
        self.fcp.parse(bytearray(b'one\x1a\x02two'))

        (end_index, splits) = self.fc.size(self.fcp.sequence, spacing=None)

        self.assertEqual((3 * 8) + (3 * 32), self.fc.x)
        self.assertEqual(0, self.fc.y)
        self.assertEqual(8, end_index)
        self.assertEqual(6, splits)
        self.assertEqual((0, 0, (3 * 8) + (3 * 32), 32),
                         self.fc.bounds)


if __name__ == '__main__':
    __name__ = os.path.basename(sys.argv[0][:-3])  # pylint: disable=redefined-builtin
    if nose:
        env = os.environ
        env['NOSE_WITH_XUNIT'] = '1'
        env['NOSE_VERBOSE'] = '1'
        exit(nose.runmodule(env=env))
    else:
        unittest.main()
