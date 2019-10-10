#!/usr/bin/python
# -*- coding: utf8 -*-

# Imports:

import os, string, argparse, subprocess, distutils.spawn, sys, shutil, random, sys, time

# Constants:

VERSION = 'v5.4.0'
SELF_PATH = '/mnt/xtra/ark/bin/video-optimizer'
VXT = ['mkv', 'mp4', 'm4v', 'mov', 'mpg', 'mpeg', 'avi', 'vob', 'mts', 'm2ts', 'wmv', 'flv', 'webm']
TEST_TIME = 300
CODEC_PRESET_X264 = 'veryfast'
CODEC_PRESET_X265 = 'medium'
VIDEO_QUALITY_X264 = 21
VIDEO_QUALITY_X264_LQ = 23
VIDEO_QUALITY_X265 = -1
CODEC_AUDIO_BITRATE_AAC = 128
CODEC_AUDIO_BITRATE_AC3 = 256
CODEC_AUDIO_BITRATE_MP3 = 256
SPANISH = 'Spanish'
ENGLISH = 'English'
JAPANESE = 'Japanese'
LATIN = 'Latin'
THUMB_POOL_SIZE = 3

if os.name == 'posix':
  FFMPEG_BIN = 'ffmpeg'
  HANDBRAKECLI_BIN = 'HandBrakeCLI'
  MEDIAINFO_BIN = 'mediainfo'
  MKVPROPEDIT_BIN = 'mkvpropedit'
  NICE_BIN = 'nice'
else:
  BIN_PATH = 'C:/script/bin/'
  FFMPEG_BIN = '%sffmpeg.exe'%(BIN_PATH)
  HANDBRAKECLI_BIN = '%sHandBrakeCLI.exe'%(BIN_PATH)
  MEDIAINFO_BIN = '%sMediaInfo.exe'%(BIN_PATH)
  MKVPROPEDIT_BIN = '%smkvpropedit.exe'%(BIN_PATH)
  NICE_BIN = ''

# Options:

parser = argparse.ArgumentParser(description = 'Video transcoder/processor (%s)'%(VERSION))
parser.add_argument('-a', nargs = 1, help = 'Audio track -first track is 0- (language chosen by default)')
parser.add_argument('-c', action = 'store_true', help = 'Cartoon mode (CODEC specific tune for cartoon movies)')
parser.add_argument('-d', action = 'store_true', help = 'Deinterlace video')
parser.add_argument('-k', action = 'store_true', help = 'Matroska (MKV) output')
parser.add_argument('-l', action = 'store_true', help = 'Low resolution (720p)')
parser.add_argument('-o', nargs = 1, help = 'Output path')
parser.add_argument('-q', nargs = 1, help = 'Quantizer factor')
parser.add_argument('-r', action = 'store_true', help = 'Rebuild original folder structure')
parser.add_argument('-s', nargs = 1, help = 'Subtitle track -first track is 0- (spanish forced searched by default)')
parser.add_argument('-t', action = 'store_true', help = 'Test mode (only the first %d s of video are processed)'%(TEST_TIME))
parser.add_argument('-w', action = 'store_true', help = 'Overwrite existing files (skip by default)')
parser.add_argument('-x', action = 'store_true', help = 'X265 codec')
parser.add_argument('-z', action = 'store_true', help = 'dry run')
parser.add_argument('--abr', nargs = 1, help = 'Audio bit rate')
parser.add_argument('--ac3', action = 'store_true', help = 'AC3 audio')
parser.add_argument('--ipadmini', action = 'store_true', help = 'iPad mini resolution (576p)')
parser.add_argument('--minitest', action = 'store_true', help = 'Mini test mode (only 10 seconds are processed)')
parser.add_argument('--mp3', action = 'store_true', help = 'MP3 audio')
parser.add_argument('--galaxy', action = 'store_true', help = 'Samsung Galaxy resolution (480p)')
parser.add_argument('--upload', action = 'store_true', help = 'Upload script to GITHUB [BETA]')
parser.add_argument('input', nargs='*', help = 'input file(s) (if missing process all video files)')
args = parser.parse_args()

FFMPEG_TEST_OPTS = ''
FFMPEG_OVERWRITE_OPTS = ''
HANDBRAKE_TEST_OPTS = ''
if args.t:
  FFMPEG_TEST_OPTS = ' -t %d '%(TEST_TIME)
  HANDBRAKE_TEST_OPTS = ' --stop-at duration:%s '%(TEST_TIME)
else:
  if args.minitest:
    FFMPEG_TEST_OPTS = ' -ss 00:02:00 -t 10 '
    HANDBRAKE_TEST_OPTS = ' --start-at duration:120 --stop-at duration:10 '
if args.w:
  FFMPEG_OVERWRITE_OPTS = ' -y '

# Auxiliar functions:

def remove_brackets(s):
  ss = s
  b = 0
  for i in range(0, len(s)):
    if s[i] == '[':
      b = 1
      x = i
    if b == 1 and s[i] == ']':
      ss = remove_brackets(s[:x] + s[i + 1:])
      break
  return ss

def language_code(name):
  if name == SPANISH:
    return 'spa'
  else:
    if name == ENGLISH:
      return 'eng'
    else:
      if name == JAPANESE:
        return 'jpn'
      else:
        if name == LATIN:
          return 'lat'
        else:
          return 'unk'

def boolean2integer(b):
  if b:
    return 1
  else:
    return 0

# Classes:

class MediaInfo:

  def __init__(self):
    self.audio_codec = []
    self.audio_languages = []
    self.audio_channels = []
    self.audio_descriptions = []
    self.audio_default = []
    self.sub_languages = []
    self.sub_formats = []
    self.sub_forced = []

  def audio_tracks_count(self):
    return len(self.audio_languages)

  def sub_tracks_count(self):
    return len(self.sub_languages)

  def print_info(self):
    print '* Media info found:'
    print '- Video width: %d (%dp)'%(self.video_width, self.video_resolution)
    for t in range(0, self.audio_tracks_count()):
      print '- Audio track %d: Codec = %s, Language = %s, Channels = %d, Audio Description = %s, Default = %s'%(t, self.audio_codec[t], self.audio_languages[t], self.audio_channels[t], self.audio_descriptions[t], self.audio_default[t])
    for t in range(0, self.sub_tracks_count()):
      print '- Subtitle track %d: Language = %s, Format = %s, Forced = %s'%(t, self.sub_languages[t], self.sub_formats[t], self.sub_forced[t])

  def select_audio_track(self, l):
    print '* Searching for %s audio track...'%(l)
    r = -1
    for i in range(0, self.audio_tracks_count()):
      if (not self.audio_descriptions[i]) and self.audio_languages[i] == l:
        if self.audio_channels[i] == 2:
          r = i
          break
    if r < 0:
      print '* Searching for %s audio track (2nd lap)...'%(l)
      for i in range(0, self.audio_tracks_count()):
        if (not self.audio_descriptions[i]) and self.audio_languages[i] == l:
          r = i
          break
    print '- Audio track selected = %d'%(r)
    return r

  def select_sub_track(self, l, f):
    print '* Searching for %s (Forced = %s) subtitle track...'%(l, f)
    r = -1
    for i in range(0, self.sub_tracks_count()):
      if self.sub_languages[i] == l and not self.sub_formats[i] == 'PGS' and self.sub_forced[i] == f:
        r = i
        break
    print '- Subtitle track selected = %d'%(r)
    return r

class MediaFile:

  def __init__(self, input_file):

    self.input_file = input_file

    # Extension extraction
    print '* Extracting file name path & extension...'
    r = os.path.splitext(self.input_file)
    n = r[0]
    input_path = r[0].rsplit('/', 1)
    if len(input_path) > 1:
      self.input_path = input_path[0] + '/'
      self.base_input_filename = input_path[1]
    else:
      self.input_path = ''
      self.base_input_filename = input_path[0]
    self.extension = r[1].lower()
    self.extension = self.extension[1:]
    r2 = os.path.splitext(self.base_input_filename)
    pre_ext = r2[1].lower()
    pre_ext = pre_ext[1:]
    if pre_ext == '4k':
      self.base_input_filename = self.base_input_filename[0:-3]
    print '- Input path: "%s"'%(self.input_path)
    print '- Base input file name: "%s"'%(self.base_input_filename)
    print '- Extension: "%s"'%(self.extension)

    # Output file calculation
    if args.o: # Output path
      d = args.o[0]
      if not d[-1] == '/':
        d += '/'
      self.output_path = d
    else:
      self.output_path = ''
    self.output_path += self.input_path
    print '- Output path: "%s"'%(self.output_path)

    self.base_output_filename = remove_brackets(self.base_input_filename)
    self.base_output_filename = self.base_output_filename.lstrip()
    self.base_output_filename = self.base_output_filename.rstrip()
    self.base_output_filename = self.base_output_filename.replace('á', 'a')
    self.base_output_filename = self.base_output_filename.replace('é', 'e')
    self.base_output_filename = self.base_output_filename.replace('í', 'i')
    self.base_output_filename = self.base_output_filename.replace('ó', 'o')
    self.base_output_filename = self.base_output_filename.replace('ú', 'u')
    self.base_output_filename = self.base_output_filename.replace('ü', 'u')
    self.base_output_filename = self.base_output_filename.replace('ñ', 'n')
    self.base_output_filename = self.base_output_filename.replace('ç', 'c')
    self.base_output_filename = self.base_output_filename.replace('Á', 'A')
    self.base_output_filename = self.base_output_filename.replace('É', 'E')
    self.base_output_filename = self.base_output_filename.replace('Í', 'I')
    self.base_output_filename = self.base_output_filename.replace('Ó', 'O')
    self.base_output_filename = self.base_output_filename.replace('Ú', 'U')
    self.base_output_filename = self.base_output_filename.replace('Ü', 'U')
    self.base_output_filename = self.base_output_filename.replace('Ñ', 'N')
    self.base_output_filename = self.base_output_filename.replace('¿', '')
    self.base_output_filename = self.base_output_filename.replace('?', '')
    self.base_output_filename = self.base_output_filename.replace('¡', '')
    self.base_output_filename = self.base_output_filename.replace('!', '')
    filename_info = ''
    if args.x:
      filename_info += 'X265 '
    if args.q:
      filename_info += 'Q{} '.format(args.q[0])
    if args.l:
      filename_info += '720p '
    if args.ipadmini:
      filename_info += '576p '
    if args.galaxy:
      filename_info += '480p '
    if args.ac3:
      filename_info += 'AC3 '
    if args.mp3:
      filename_info += 'MP3 '
    if args.abr:
      filename_info += '{}K '.format(args.abr[0])
    if filename_info != '':
      self.base_output_filename += ' [%s]'%(filename_info.rstrip())

    if not args.o:
      self.output_file = self.output_path + self.base_output_filename
    else:
      self.output_file = self.output_path + self.base_output_filename
    if args.k:
      self.output_file += '.mkv'
    else:
      self.output_file += '.mp4'

    print '- Output file name: "%s"'%(self.output_file)

    # Movie name:
    tmp_movie_name = self.base_input_filename.split('[')
    tmp_movie_name = tmp_movie_name[0].rstrip()
    movnamyea = tmp_movie_name
    movnamyea = movnamyea.split('/')
    movnamyea = movnamyea[-1]
    movnamyea = movnamyea.split('\\')
    movnamyea = movnamyea[-1]
    movnam = movnamyea
    self.movie_name = movnam
    print '- Extracted title: "%s"'%(self.movie_name)

    # Media info extraction
    self.info = MediaInfo()
    if self.extension == 'mkv' or self.extension == 'mp4' or self.extension == 'avi' or self.extension == 'wmv':
      print '> Extracting file media info...'
      # Video width
      o = subprocess.check_output('%s --Inform="Video;%%Width%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      try:
        self.info.video_width = int(o)
      except:
        self.info.video_width = 0
      if self.info.video_width > 3000:
        self.info.video_resolution = 2160
      else:
        if self.info.video_width > 1500:
          self.info.video_resolution = 1080
        else:
          self.info.video_resolution = 720
      # Audio tracks count
      o = subprocess.check_output('%s --Inform="General;%%AudioCount%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      try:
        audcnt = int(o)
      except:
        audcnt = 0
      print '- Audio tracks found = %d'%(audcnt)
      # Audio CODECs
      o = subprocess.check_output('%s --Inform="General;%%Audio_Format_List%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      o = o.split(' / ')
      for i in range(0, audcnt):
        self.info.audio_codec.append(o[i])
      # Audio Languages
      o = subprocess.check_output('%s --Inform="General;%%Audio_Language_List%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      o = o.split(' / ')
      for i in range(0, audcnt):
        if len(o) >= i + 1:
          if o[i] == '':
            o[i] = 'Unknown'
        else:
          o.append('Unknown')
        self.info.audio_languages.append(o[i])
      # Audio Channels
      o = subprocess.check_output('%s --Inform="Audio;%%Channel(s)%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      for i in range(0, audcnt):
        try:
          channels_amount = int(o[0:1])
        except:
          channels_amount = 0
        self.info.audio_channels.append(channels_amount)
        if o[1:4] == ' / ':
          o = o[5:]
        else:
          o = o[1:]
      # Audiodescription
      o = subprocess.check_output('%s --Inform="Audio;%%Title%%***" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      s = o.split('***')
      for t in range(0, len(s) - 1):
        if ('descri' in s[t].lower()) or ('comenta' in s[t].lower()) or ('comment' in s[t].lower()) or ('invidente' in s[t].lower()):
          self.info.audio_descriptions.append(True)
        else:
          self.info.audio_descriptions.append(False)
      # Audio default
      o = subprocess.check_output('%s --Inform="Audio;%%Default%%/" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      o = o.split('/')
      self.info.audio_default = []
      for i in range(0, len(o) - 1):
        if o[i] == 'Yes':
          self.info.audio_default.append(True)
        else:
          self.info.audio_default.append(False)
      # Subtitle tracks count
      o = subprocess.check_output('%s --Inform="General;%%TextCount%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      if o == '':
        subcnt = 0
      else:
        subcnt = int(o)
      print '- Subtitle tracks found = %d'%(subcnt)
      if subcnt == 0:
        self.info.sub_languages = []
        self.info.sub_forced = []
      else:
        # Subtitle languages
        o = subprocess.check_output('%s --Inform="General;%%Text_Language_List%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
        o = o.rstrip()
        o = o.split(' / ')
        self.info.sub_languages = o
        # Subtitle formats
        o = subprocess.check_output('%s --Inform="General;%%Text_Format_List%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
        o = o.rstrip()
        o = o.split(' / ')
        self.info.sub_formats = o
        # Subtitle forced (by "Forced" field)
        o = subprocess.check_output('%s --Inform="Text;%%Forced%%/" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
        o = o.rstrip()
        o = o.split('/')
        self.info.sub_forced = []
        for i in range(0, len(o) - 1):
          if o[i] == 'Yes':
            self.info.sub_forced.append(True)
          else:
            self.info.sub_forced.append(False)
        # Subtitle forced (by "Title" field)
        o = subprocess.check_output('%s --Inform="Text;%%Title%%/" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
        o = o.rstrip()
        o = o.split('/')
        for i in range(0, len(o) - 1):
          if ('forz' in o[i].lower()) or ('forc' in o[i].lower()):
            self.info.sub_forced[i] = True
      self.info.print_info()

  # MAIN TRANSCODING ROUTINE *****
  def transcode(self, input_file, aud_list, sub_list):
    print '* Transcoding media file "%s" to "%s"...'%(input_file, self.output_file)

    if args.x:
      codec_pre = CODEC_PRESET_X265
      quantizer = VIDEO_QUALITY_X265
    else:
      codec_pre = CODEC_PRESET_X264
      if args.l or args.ipadmini or args.galaxy:
        quantizer = VIDEO_QUALITY_X264_LQ
      else:
        quantizer = VIDEO_QUALITY_X264

    if args.q:
      quantizer = int(args.q[0])

    if args.ac3:
      audio_br = CODEC_AUDIO_BITRATE_AC3
    else:
      if args.mp3:
        audio_br = CODEC_AUDIO_BITRATE_MP3
      else:
        audio_br = CODEC_AUDIO_BITRATE_AAC
    if args.abr:
      audio_br = int(args.abr[0])

    options = ''
    options += ' --loose-anamorphic --modulus 2 --crop 0:0:0:0'
    options += ' --encoder-preset {} --cfr'.format(codec_pre)

    if args.x:
      options += ' --encoder x265'
    else:
      options += ' --encoder x264 --encoder-profile high --encoder-level 4.1'

    if args.l:
      options += ' --maxWidth 1280'
    else:
      if args.ipadmini:
        options += ' --maxWidth 1024'
      else:
        if args.galaxy:
          options += ' --maxWidth 800'
        else:
          options += ' --width 1920'

    if args.x:
      if args.c:
        options += ' --encopts psy-rd=0.4:aq-strength=0.4:deblock=1,1:bframes=6'
    else:
      if args.c:
        options += ' --encoder-tune animation'
      else:
        options += ' --encoder-tune film'

    if quantizer >= 0:
      options += ' --quality {}'.format(quantizer)

    if args.d:
      options += ' --deinterlace'

    audopts = ' --mixdown stereo'
    if args.ac3:
      audopts += ' --aencoder ac3'
    if args.mp3:
      audopts += ' --aencoder mp3'
    if audio_br >= 0:
      audopts += ' --ab {}'.format(audio_br)
    if len(aud_list) > 0:
      audopts += ' --audio '
      for n in range(0, len(aud_list)):
        audopts += '%d,'%(aud_list[n] + 1)
      audopts = audopts[:-1]

    subopts = ''
    if len(sub_list) > 0:
      subopts += ' --subtitle '
      for n in range(0, len(sub_list)):
        subopts += '%d,'%(sub_list[n] + 1)
      subopts = subopts[:-1]
    if sub_list:
      if self.info.sub_forced[sub_list[0]]:
        subopts += ' --subtitle-burned'

    c = '%s %s -i "%s" --optimize --markers %s%s%s -o "%s"'%(HANDBRAKECLI_BIN, HANDBRAKE_TEST_OPTS, input_file, options, audopts, subopts, self.output_file)
    execute_command(c)

  def tag(self, aud_list, sub_list, output_file):
    if self.extension == 'mkv':
      movnamyea = self.movie_name
      movnamyea = movnamyea.split('/')
      movnamyea = movnamyea[-1]
      movnamyea = movnamyea.split('\\')
      movnamyea = movnamyea[-1]
      movnam = movnamyea
      c = '%s "%s" --edit info --set title="%s"'%(MKVPROPEDIT_BIN, output_file, movnam)
      execute_command(c)
      # Audio tracks
      for n in range(0, len(aud_list)):
        name = self.info.audio_languages[aud_list[n]]
        code = language_code(name)
        defa = boolean2integer(n == 0)
        forc = boolean2integer(n == 0)
        if forc == 1:
          name += ' Forced'
        if defa == 1:
          name += ' Default'
        c = '%s "%s" --edit track:a%d --set name="%s"'%(MKVPROPEDIT_BIN, output_file, n + 1, name)
        execute_command(c)
        c = '%s "%s" --edit track:a%d --set language=%s'%(MKVPROPEDIT_BIN, output_file, n + 1, code)
        execute_command(c)
        c = '%s "%s" --edit track:a%d --set flag-default=%d'%(MKVPROPEDIT_BIN, output_file, n + 1, defa)
        execute_command(c)
        c = '%s "%s" --edit track:a%d --set flag-forced=%d'%(MKVPROPEDIT_BIN, output_file, n + 1, forc)
        execute_command(c)
      # Subtitle tracks
      for n in range(0, len(sub_list)):
        name = self.info.sub_languages[sub_list[n]]
        code = language_code(name)
        defa = boolean2integer(n == 0)
        forc = boolean2integer(self.info.sub_forced[sub_list[n]])
        if forc == 1:
          name += ' Forced'
        if defa == 1:
          name += ' Default'
        c = '%s "%s" --edit track:s%d --set name="%s"'%(MKVPROPEDIT_BIN, output_file, n + 1, name)
        execute_command(c)
        c = '%s "%s" --edit track:s%d --set language=%s'%(MKVPROPEDIT_BIN, output_file, n + 1, code)
        execute_command(c)
        c = '%s "%s" --edit track:s%d --set flag-default=%d'%(MKVPROPEDIT_BIN, output_file, n + 1, defa)
        execute_command(c)
        c = '%s "%s" --edit track:s%d --set flag-forced=%d'%(MKVPROPEDIT_BIN, output_file, n + 1, forc)
        execute_command(c)

# Subroutines:

def execute_command(c):
  if NICE_BIN != '':
    c = NICE_BIN + ' -n 19 ' + c
  print '> Executing: %s'%(c)
  if not args.z:
    os.system(c)

def transcode_video_file(f):

  v = MediaFile(f)

  if v.extension in VXT:
    if not args.w and os.path.isfile(v.output_file):
      print '* Destination file already exists (skipping)'
      return
  else:
    print '* ERROR: input file is not a video file (skipping)'
    return

  # Audio/sub tracks processing:

  track_audio_spa = v.info.select_audio_track(SPANISH)
  track_audio_eng = v.info.select_audio_track(ENGLISH)
  track_audio_jpn = v.info.select_audio_track(JAPANESE)
  track_sub_spa   = v.info.select_sub_track(SPANISH, False)
  track_sub_spa_f = v.info.select_sub_track(SPANISH, True)
  track_sub_lat_f = v.info.select_sub_track(LATIN, True)

  track_audio = 0
  if track_audio_jpn >= 0: # Japanese audio
    track_audio = track_audio_jpn
  if track_audio_eng >= 0: # English audio
    track_audio = track_audio_eng
  if track_audio_spa >= 0: # Spanish audio
    track_audio = track_audio_spa
  if args.a: # Audio track selected by user
    track_audio = int(args.a[0])
  aud_list = [track_audio]

  sub_list = []
  if track_sub_spa_f >= 0:
    sub_list.append(track_sub_spa_f)
  else:
    if track_audio_spa < 0 and track_sub_lat_f >= 0:
      sub_list.append(track_sub_lat_f)

  print ''
  print '<<<<<<<<<< TRANSCODING PLANNING >>>>>>>>>>'
  print ' - Input file: "%s"'%(v.input_file)
  print ' - Output file: "%s"'%(v.output_file)
  if args.l:
    print ' - Video resolution: 720p'
  else:
    if args.ipadmini:
      print ' - Video resolution: 576p'
    else:
      if args.galaxy:
        print ' - Video resolution: 480p'
      else:
        print ' - Video resolution: 1080p'
  if v.info.audio_languages:
    print ' - Audio language: %s'%(v.info.audio_languages[aud_list[0]])
  if not sub_list:
    print ' - Subtitle language: no suitable subtitles found'
  else:
    print ' - Subtitle language: {} (BURNED = {})'.format(v.info.sub_languages[sub_list[0]], v.info.sub_forced[sub_list[0]])
  print '<<<<<<<<<< -------------------- >>>>>>>>>>'
  print ''
  if not args.z:
    wait_counter = 5
    while wait_counter > 0:
      sys.stdout.write('\r* Starting transcoding in %02d s...'%(wait_counter))
      sys.stdout.flush()
      time.sleep(1)
      wait_counter -= 1
  v.transcode(f, aud_list, sub_list)

  if args.k: # Post-tagging if MKV output:
    v.tag(aud_list, [], v.output_file)

def process_file(f):
  transcode_video_file(f)

def process_directory(dir):
  lis = os.listdir(dir)
  lis.sort()
  for arc in lis:
    rut = dir + '/' + arc
    if os.path.isdir(rut):
      if args.o:
        nueva_ruta = rut
        if nueva_ruta[0] == '.':
          nueva_ruta = nueva_ruta[1:]
        nueva_ruta = args.o[0] + nueva_ruta
        if args.r and not os.path.exists(nueva_ruta):
          print "Creating directory: %s"%(nueva_ruta)
          if not args.z:
            os.makedirs(nueva_ruta)
      process_directory(rut)
    else:
      process_file(rut)

def verify_software(b, critical):
  if not b == '':
    print 'Checking for "%s"...'%(b),
    if distutils.spawn.find_executable(b) is None:
      if critical:
        sys.exit('MISSING!')
      else:
        print 'MISSING! (WARNING)'
    else:
      print 'OK'

# Main routine:

verify_software(HANDBRAKECLI_BIN, True)
verify_software(MEDIAINFO_BIN, True)
verify_software(MKVPROPEDIT_BIN, True)
verify_software(NICE_BIN, True)

if args.upload:
  try:
    os.chdir(SELF_PATH)
  except:
    print 'Error changing to source directory.'
  c = 'git commit -a -m "%s" ; git push'%(VERSION)
  execute_command(c)
else:
  if args.input:
    for f in args.input:
      process_file(f)
  else:
    process_directory('.')
