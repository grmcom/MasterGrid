#!/usr/bin/python
'''
MasterGrid
Copyright (c) 2015 Robert Oscilowski

Multitouch MIDI keyboard using Kivy.

MasterGrid is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

MasterGrid is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with MasterGrid. If not, see <http://www.gnu.org/licenses/>
'''

import kivy
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.uix.gridlayout import GridLayout
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.settings import SettingItem
from kivy.uix.popup import Popup
from kivy.properties import ObjectProperty, NumericProperty
import pygame.midi

class Key(Button):
    index = NumericProperty()

class Grid(GridLayout):
    app = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(Grid, self).__init__(**kwargs)
        pygame.midi.init()
        self.set_midi_device()
        self.channel = self.app.config.getint('MIDI', 'Channel')
        self.velocity = self.app.config.getint('MIDI', 'Velocity')
        self.sensitivity = self.app.config.getint('MIDI', 'Sensitivity')
        self.aftertouch = self.app.config.getboolean('MIDI', 'Aftertouch')

    def set_midi_device(self):
        c = pygame.midi.get_count()
        id_device_from_settings = -1
        print('%s midi devices found' % c)
        for i in range(c):
            if pygame.midi.get_device_info(i)[1].decode() == self.app.config.get('MIDI', 'Device'):
                id_device_from_settings = i
        print('Default is %s' % pygame.midi.get_device_info(pygame.midi.get_default_output_id())[1].decode())

        if id_device_from_settings != -1:
            self.midi_device = id_device_from_settings
            print('MIDI device "%s" found. Connecting.' % pygame.midi.get_device_info(id_device_from_settings)[1].decode())
        else:
            self.midi_device = pygame.midi.get_default_output_id()
            print('Warning: No MIDI device named "%s" found. Choosing the system default ("%s").' % (self.app.config.get('MIDI', 'Device'), pygame.midi.get_device_info(self.midi_device)[1].decode()))

        if pygame.midi.get_device_info(self.midi_device)[4] == 1:
            print('Error: Unable to open MIDI device - Already in use!')

        self.midi_out = pygame.midi.Output(self.midi_device)

    def which_note(self, touch):
        for key in self.children:
            if key.collide_point(*touch):
                return key.index
        return None

    def same_note(self, touch1, touch2):
        return self.which_note(touch1) == self.which_note(touch2)

    def new_note(self, touch):
        return True if not self.same_note(touch.pos, touch.ppos) else False

    def note_center(self, touch):
        for key in self.children:
            if key.collide_point(*touch):
                return key.center_y

    def cur(self, touch):
        return self.which_note(touch.pos)

    def prev(self, touch):
        return self.which_note(touch.ppos)

    def pressure(self, touch):
        if self.aftertouch:
            return self.velocity - round(abs(self.note_center(touch.pos) - touch.y)) * self.sensitivity
        else:
            return self.velocity

    def note_on(self, note, velocity, channel):
        return self.midi_out.note_on(note, velocity, self.channel)

    def note_off(self, note, channel):
        return self.midi_out.note_off(note, 0, self.channel)

    def on_touch_down(self, touch):
        if self.cur(touch):
            self.note_on(self.cur(touch), self.pressure(touch), self.channel)

    def on_touch_up(self, touch):
        if self.cur(touch):
            self.note_off(self.cur(touch), self.channel)

    def on_touch_move(self, touch):
        if self.cur(touch) and self.prev(touch):
            if self.new_note(touch):
                self.note_off(self.prev(touch), self.channel)
                self.note_on(self.cur(touch), self.pressure(touch), self.channel)
            if self.aftertouch:
                self.midi_out.write_short(0xA0 + self.channel, self.cur(touch), self.pressure(touch))

class SettingMIDI(SettingItem):
    '''Implementation of an option list in top of :class:`SettingItem`.
    A label is used on the setting to show the current choice, and when you
    touch on it, a Popup will open with all the options displayed in list.
    '''

    '''
    :data:`options` is a :class:`~kivy.properties.ListProperty`, default to []
    '''

    popup = ObjectProperty(None, allownone=True)
    '''(internal) Used to store the current popup when it's shown

    :data:`popup` is a :class:`~kivy.properties.ObjectProperty`, default to
    None.
    '''

    def on_panel(self, instance, value):
        if value is None:
            return
        self.bind(on_release=self._create_popup)

    def _set_option(self, instance):
        self.value = instance.text
        # don't set the MIDI output here, but in the on_setting_change function!
        self.popup.dismiss()

    def _create_popup(self, instance):
        # create the popup containing a BoxLayout
        content = BoxLayout(orientation='vertical', spacing=10)
        self.popup = popup = Popup(content=content,
            title=self.title, size_hint=(None, None), size=(400, 400))
        popup.height = pygame.midi.get_count() * 30 + 150

        # add a spacer
        content.add_widget(Widget(size_hint_y=None, height=1))
        uid = str(self.uid)

        device_count = pygame.midi.get_count()

        # add all the selectable MIDI output devices
        for i in range(device_count):
            if pygame.midi.get_device_info(i)[3] == 1 and (pygame.midi.get_device_info(i)[4] == 0 or pygame.midi.get_device_info(i)[1] == self.value):
                # if it's an output device and it's not already opened (unless it's the device opened by ME), display it in list.
                # if this is the device that was selected before, display it pressed
                state = 'down' if pygame.midi.get_device_info(i)[1].decode() == self.value else 'normal'
                btn = ToggleButton(text=str(pygame.midi.get_device_info(i)[1].decode()), state=state, group=uid)
                btn.bind(on_release=self._set_option)
                content.add_widget(btn)

        # finally, add a cancel button to return on the previous panel
        btn = Button(text='Cancel', size_hint_y=None, height=50)
        btn.bind(on_release=popup.dismiss)
        content.add_widget(btn)

        # and open the popup !
        popup.open()

class MasterGrid(App):
    title = 'MasterGrid'

    def __init(self, **kwargs):
        super(MasterGrid, self).__init__(**kwargs)
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down)

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        if keycode[1] == 'spacebar':
            Window.toggle_fullscreen()
        elif keycode[1] == 'tab':
            self.open_settings()
        elif keycode[1] == 'escape':
            quit()

    def build(self):
        rows = self.config.getint('MIDI', 'Rows')
        keys = self.config.getint('MIDI', 'Keys')
        lownote = self.config.getint('MIDI', 'LowNote')
        interval = self.config.getint('MIDI', 'Interval')

        notenames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        black = [0,0,0,1]
        white = [255,255,255,1]

        grid = Grid(app=self, rows=rows, cols=keys)

        for row in reversed(range(rows)):
            for note in reversed(range(lownote, lownote + keys)):
                accidental = True if note % 12 in [1, 3, 6, 8, 10] else False
                keycolor = black if accidental else white
                textcolor = white if accidental else black
                label = notenames[note % 12]
                key = Key(index=note, text=label, background_color=keycolor, color=textcolor)
                grid.add_widget(key, len(grid.children))
            lownote += interval

        return grid

    def resize_grid(self):
        self.clear_widgets()
        self.build()

    def build_config(self, config):
        config.adddefaultsection('MIDI')
        config.setdefault('MIDI', 'Device', 'ZynAddSubFX')
        config.setdefault('MIDI', 'Channel', '0')
        config.setdefault('MIDI', 'Velocity', '127')
        config.setdefault('MIDI', 'Aftertouch', True)
        config.setdefault('MIDI', 'Sensitivity', '3')
        config.setdefault('MIDI', 'Rows', '13')
        config.setdefault('MIDI', 'Keys', '25')
        config.setdefault('MIDI', 'LowNote', '24')
        config.setdefault('MIDI', 'Interval', '5')

    def build_settings(self, settings):
        settings.register_type('midi', SettingMIDI)
        settings.add_json_panel('MasterGrid Settings', self.config, data='''[
            { "type": "midi", "title": "MIDI output device", "desc": "Device to use for MIDI", "section": "MIDI", "key": "Device"},
            { "type": "numeric", "title": "MIDI channel", "desc": "MIDI channel to send data to [0 - 15]", "section": "MIDI", "key": "Channel"},
            { "type": "numeric", "title": "Velocity", "desc": "Default velocity of the midi notes", "section": "MIDI", "key": "Velocity"},
            { "type": "bool", "title": "Aftertouch", "desc": "Make notes decrease in volume as touch moves away from the key's vertical center", "section": "MIDI", "key": "Aftertouch"},
            { "type": "numeric", "title": "Aftertouch Sensitivity", "desc": "Velocity change multiplier [1 - 4]", "section": "MIDI", "key": "Sensitivity"},
            { "type": "numeric", "title": "Lowest Note", "desc": "MIDI note number of the first note (bottom left key)", "section": "MIDI", "key": "LowNote"},
            { "type": "numeric", "title": "Rows", "desc": "Number of rows of keys", "section": "MIDI", "key": "Rows"},
            { "type": "numeric", "title": "Keys per row", "desc": "Number of notes per row", "section": "MIDI", "key": "Keys"},
            { "type": "numeric", "title": "Interval", "desc": "How many notes to shift each new row starting from the bottom", "section": "MIDI", "key": "Interval"}
        ]''')

    def on_config_change(self, config, section, key, value):
        token = (section, key)
        if token == ('MIDI', 'Device'):
            self.set_midi_device()
        elif token == ('MIDI', 'Channel'):
            pass
        elif token == ('MIDI', 'Velocity'):
            pass
        elif token == ('MIDI', 'Aftertouch'):
            pass
        elif token == ('MIDI', 'Sensitivity'):
            pass
        elif token == ('MIDI', 'LowNote'):
            self.resize_grid()
        elif token == ('MIDI', 'Rows'):
            self.resize_grid()
        elif token == ('MIDI', 'Keys'):
            self.resize_grid()
        elif token == ('MIDI', 'Interval'):
            self.resize_grid()

if __name__ in ('__main__', '__android__'):
    MasterGrid().run()
