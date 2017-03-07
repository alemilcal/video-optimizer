#!/usr/bin/python
# -*- coding: utf8 -*-

# Imports:

import os, string, argparse, subprocess, distutils.spawn, sys, shutil, random

def generate_random_filename(prefix, suffix):
  b = True
  while b:
    s = '%s%08d%s'%(prefix, random.randint(0,99999999), suffix)
    b = os.path.exists(s)
  return s

# Constants:

VERSION = 'v4.13.6'
VXT = ['mkv', 'mp4', 'm4v', 'mov', 'mpg', 'mpeg', 'avi', 'vob', 'mts', 'm2ts', 'wmv']
TEST_TIME = 300 # 300 seg = 5 min
VIDEO_QUALITY = 23
#VIDEO_QUALITY_HD = 21
GAIN = '3.0'
DRC = '2.0'
SPANISH = 'Spanish'
ENGLISH = 'English'
TEMP_REMUX_FILE = generate_random_filename('temp_rmux_', '.mkv')
TEMP_AV_FILE_0 = generate_random_filename('temp_avf1_', '.mkv')
TEMP_AV_FILE_1 = generate_random_filename('temp_avf2_', '.mkv')
TEMP_BIF_DIR = generate_random_filename('temp_bifd_', '')
THUMB_POOL_SIZE = 3

if os.name == 'posix':
  FFMPEG_BIN = 'ffmpeg'
  HANDBRAKECLI_BIN = 'HandBrakeCLI'
  MEDIAINFO_BIN = 'mediainfo'
  MKVPROPEDIT_BIN = 'mkvpropedit'
  NICE_BIN = 'nice'
  SED_BIN = 'sed'
  BIFTOOL_BIN = 'biftool'
else:
  BIN_PATH = 'C:/script/bin/'
  FFMPEG_BIN = '%sffmpeg.exe'%(BIN_PATH)
  HANDBRAKECLI_BIN = '%sHandBrakeCLI.exe'%(BIN_PATH)
  MEDIAINFO_BIN = '%sMediaInfo.exe'%(BIN_PATH)
  MKVPROPEDIT_BIN = '%smkvpropedit.exe'%(BIN_PATH)
  NICE_BIN = ''
  SED_BIN = '%ssed.exe'%(BIN_PATH)
  BIFTOOL_BIN = '%sbiftool.exe'%(BIN_PATH)

# Options:

parser = argparse.ArgumentParser(description = 'Video transcoder/processor (%s)'%(VERSION))
parser.add_argument('-a', nargs = 1, help = 'audio track (language chosen by default)')
parser.add_argument('-b', action = 'store_true', help = 'Generate BIF files [BETA]')
parser.add_argument('-e', action = 'store_true', help = 'English + Spanish (Dual audio/subtitles)')
parser.add_argument('-f', action = 'store_true', help = 'Full HD output (1080p) if available in source')
parser.add_argument('-g', action = 'store_true', help = 'Debug mode')
parser.add_argument('-k', action = 'store_true', help = 'Matroska (MKV) output')
parser.add_argument('-m', action = 'store_true', help = 'Skip adding metadata')
parser.add_argument('-o', nargs = 1, help = 'Output path')
parser.add_argument('-p', action = 'store_true', help = 'Prioritize default audio tracks (instead looking for adequate amount of channels)')
parser.add_argument('-q', nargs = 1, help = 'Quality factor (%d by default)'%(VIDEO_QUALITY))
parser.add_argument('-r', action = 'store_true', help = 'Rebuild original folder structure')
#parser.add_argument('-s', nargs = 1, help = 'Subtitle track (spanish forced searched by default / 0 disables subs)')
parser.add_argument('--nosub', action = 'store_true', help = 'No subtitles')
parser.add_argument('-t', action = 'store_true', help = 'Test mode (only the first %d s of video are processed)'%(TEST_TIME))
parser.add_argument('--noenc', action = 'store_true', help = 'No video encoding (passthrough) [BETA]')
parser.add_argument('--noren', action = 'store_true', help = 'No file renaming (instead of removing brackets) [BETA]')
parser.add_argument('--subext', action = 'store_true', help = 'Extract subtitle tracks to external files also [BETA]')
parser.add_argument('--tagonly', action = 'store_true', help = 'Tag file name only (no transcoding) [BETA]')
parser.add_argument('-w', action = 'store_true', help = 'Overwrite existing files (skip by default)')
parser.add_argument('-x', action = 'store_true', help = 'X265 codec [BETA]')
parser.add_argument('-z', action = 'store_true', help = 'dry run')
parser.add_argument('input', nargs='*', help = 'input file(s) (if missing process all video files)')
args = parser.parse_args()

FFMPEG_TEST_OPTS = ''
HANDBRAKE_TEST_OPTS = ''
if args.t:
  FFMPEG_TEST_OPTS = ' -t %d '%(TEST_TIME)
  HANDBRAKE_TEST_OPTS = ' --stop-at duration:%s '%(TEST_TIME)

# Auxiliar functions:

def language_code(name):
  if name == SPANISH:
    return 'spa'
  else:
    if name == ENGLISH:
      return 'eng'
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
    self.sub_forced = []

  def audio_tracks_count(self):
    return len(self.audio_languages)

  def sub_tracks_count(self):
    return len(self.sub_languages)

  def print_info(self):
    print '* Media info found:'
    for t in range(0, self.audio_tracks_count()):
      print '- Audio track %d: Codec = %s, Language = %s, Channels = %d, Audio Description = %s, Default = %s'%(t, self.audio_codec[t], self.audio_languages[t], self.audio_channels[t], self.audio_descriptions[t], self.audio_default[t])
    for t in range(0, self.sub_tracks_count()):
      print '- Subtitle track %d: Language = %s, Forced = %s'%(t, self.sub_languages[t], self.sub_forced[t])

  def select_audio_track(self, l):
    print '* Searching for %s audio track...'%(l)
    r = -1
    for i in range(0, self.audio_tracks_count()):
      if not args.p:
        if (not self.audio_descriptions[i]) and self.audio_languages[i] == l:
          #if (args.d and self.audio_channels[i] == 6) or ((not args.d) and self.audio_channels[i] == 2):
          if self.audio_channels[i] == 2:
            r = i
            break
      else: # Prioritize default audio tracks
        if self.audio_languages[i] == l and self.audio_default[i]:
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
      if self.sub_languages[i] == l and self.sub_forced[i] == f:
        r = i
        break
    print '- Subtitle track selected = %d'%(r)
    return r

class MediaFile:

  def __init__(self, input_file):

    self.input_file = input_file

    # Extension extraction
    print '* Extracting extension...'
    r = os.path.splitext(self.input_file)
    n = r[0]
    self.extension = r[1].lower()
    self.extension = self.extension[1:]
    print '- Extension found: %s'%(self.extension)

    # Output file calculation
    if args.o: # Output path
      if not args.r: # Rebuild original folder structure
        d = args.o[0]
        if not d[-1] == '/' and not d == '\\':
          d += '\\'
        n = d + os.path.basename(n)
      else:
        if n[0] == '.':
          n = n[1:]
        n = args.o[0] + n
    self.base_filename = n
    self.output_bif_file = self.base_filename + '.bif'
    self.output_jpg_file = self.base_filename + '.jpg'
    if args.noren:
      self.output_file = self.base_filename
    else:
      self.output_file = self.base_filename.split(' [')[0]
      self.output_file = self.output_file.replace('á', 'a')
      self.output_file = self.output_file.replace('é', 'e')
      self.output_file = self.output_file.replace('í', 'i')
      self.output_file = self.output_file.replace('ó', 'o')
      self.output_file = self.output_file.replace('ú', 'u')
      self.output_file = self.output_file.replace('ü', 'u')
      self.output_file = self.output_file.replace('ñ', 'n')
      self.output_file = self.output_file.replace('ç', 'c')
      self.output_file = self.output_file.replace('Á', 'A')
      self.output_file = self.output_file.replace('É', 'E')
      self.output_file = self.output_file.replace('Í', 'I')
      self.output_file = self.output_file.replace('Ó', 'O')
      self.output_file = self.output_file.replace('Ú', 'U')
      self.output_file = self.output_file.replace('Ü', 'U')
      self.output_file = self.output_file.replace('Ñ', 'N')
      self.output_file = self.output_file.replace('¿', '')
      self.output_file = self.output_file.replace('?', '')
      self.output_file = self.output_file.replace('¡', '')
      self.output_file = self.output_file.replace('!', '')
    self.output_file += ' '
    if args.f:
      self.output_file += '[FullHD]'
    if args.x:
      self.output_file += '[X265]'
    if args.q:
      self.output_file += '[Q%s]'%(args.q[0])
    if args.noren:
      self.output_file += '[OV]'
    if args.k:
      self.output_file += '[OV].mkv'
      #self.output_file += '.mkv'
    else:
      #self.output_file += '[OV].mp4'
      self.output_file += '.mp4'
    # Movie name:
    tmp_movie_name = n.split(' [')[0]
    tmp_movie_name = tmp_movie_name.split('/')
    #print tmp_movie_name
    self.movie_name = tmp_movie_name[-1]

    # Media info extraction
    self.info = MediaInfo()
    if True: #self.extension == 'mkv':
      print '> Extracting file media info...'
      # Audio tracks count
      o = subprocess.check_output('%s --Inform="General;%%AudioCount%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      audcnt = int(o)
      # Audio CODECs
      o = subprocess.check_output('%s --Inform="General;%%Audio_Format_List%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      #print '*'+o+'*'
      o = o.rstrip()
      o = o.split(' / ')
      for i in range(0, audcnt):
        self.info.audio_codec.append(o[i])
      # Audio Languages
      o = subprocess.check_output('%s --Inform="General;%%Audio_Language_List%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      #print o
      o = o.rstrip()
      o = o.split(' / ')
      for i in range(0, audcnt):
        if o[i] == '':
          o[i] = 'Unknown'
        self.info.audio_languages.append(o[i])
      #print self.info.audio_languages
      # Audio Channels
      o = subprocess.check_output('%s --Inform="Audio;%%Channel(s)%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      #print '*'+o+'*'
      for i in range(0, audcnt):
        self.info.audio_channels.append(int(o[0:1]))
        if o[1:4] == ' / ':
          o = o[5:]
        else:
          o = o[1:]
      # Audiodescription
      o = subprocess.check_output('%s --Inform="Audio;%%Title%%***" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      s = o.split('***')
      for t in range(0, len(s) - 1):
        if ('descri' in s[t].lower()) or ('comenta' in s[t].lower()) or ('comment' in s[t].lower()):
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

  def transcode(self, input_file, aud_list, sub_list):
    print '* Transcoding media file "%s" to "%s"...'%(input_file, self.output_file)
    #options = ' --audio-fallback ffac3 --loose-anamorphic --modulus 2 --x264-preset fast --h264-profile high --h264-level 4.1'
    options = ' --aencoder av_aac --loose-anamorphic --modulus 2 --x264-preset fast --h264-profile high --h264-level 4.1'
    if args.x:
      options += ' --encoder x265 '
    else:
      options += ' --encoder x264 '
    if args.f:
      options += ' --maxWidth 1920 '
    else:
      options += ' --maxWidth 1280 '
    if args.q:
      quantizer = int(args.q[0])
    else:
      #if args.f:
      #  quantizer = VIDEO_QUALITY_HD
      #else:
      quantizer = VIDEO_QUALITY
    if args.x:
      quantizer = quantizer + 1
    options += ' --quality %d '%(quantizer)
    if args.noenc:
      #if args.d or args.v:
      #  audopts = ' -c:a copy '
      #else:
      audopts = ' -B 128 '
    else:
      #if args.d or args.v:
      #  audopts = ' --aencoder copy '
      #else:
      audopts = ' --mixdown stereo -B 128 --gain %s --drc %s '%(GAIN, DRC)
      if len(aud_list) > 0:
        audopts += ' --audio '
        for n in range(0, len(aud_list)):
          #if REMUX_MODE:
          #  audopts += '%d,'%(n + 1)
          #else:
          audopts += '%d,'%(aud_list[n] + 1)
        audopts = audopts[:-1]
    subopts = ''
    if len(sub_list) > 0:
      subopts += ' --subtitle '
      for n in range(0, len(sub_list)):
        subopts += '%d,'%(n + 1)
      subopts = subopts[:-1]
    if args.noenc:
      c = '%s %s -i "%s" -map 0:v:0 -c:v copy -map 0:a %s -map 0:s -c:s copy "%s"'%(FFMPEG_BIN, FFMPEG_TEST_OPTS, input_file, audopts, self.output_file)
    else:
      c = '%s %s -i "%s" --optimize --markers %s %s %s -o "%s"'%(HANDBRAKECLI_BIN, HANDBRAKE_TEST_OPTS, input_file, options, audopts, subopts, self.output_file)
    execute_command(c)

  def transcode_audio_track(self, audio_track, sub_tracks, output_file):
    print '* Transcoding audio track %d to "%s"'%(audio_track, output_file)
    if self.info.audio_channels == []:
      codec = 'copy'
      panopts = ''
    else:
      if self.info.audio_channels[audio_track] == 2: # Stereo source
        if args.v:
          #codec = 'libfaac'
          codec = 'aac -strict experimental'
          panopts = '-af "pan=stereo|c0<0.5*c0+0.5*c3+c1+0.5*c5|c1<0.5*c2+0.5*c4+c1+0.5*c5"'
        else:
          codec = 'copy'
          panopts = ''
      else: # Surround source
        #if args.d:
        #  codec = 'ac3'
        #  panopts = '-af "pan=3.1|c0<0.5*c0+0.5*c3|c1<c1|c2<0.5*c2+0.5*c4|c3<c5"'
        #else:
        #if args.v:
        #  #codec = 'libfaac'
        #  codec = 'aac -strict experimental'
        #  panopts = '-af "pan=stereo|c0<0.5*c0+0.5*c3+c1+0.5*c5|c1<0.5*c2+0.5*c4+c1+0.5*c5"'
        #else:
        codec = 'copy'
        panopts = ''
    if len(sub_tracks) > 0:
      subopts = ' -c:s copy '
      for i in range(0, len(sub_tracks)):
        subopts += ' -map 0:s:%d '%(sub_tracks[i])
    else:
      subopts = ''
    c = '%s %s -threads 4 -y -i "%s" -vn -c:a %s %s -map 0:a:%d %s -f matroska "%s"'%(FFMPEG_BIN, FFMPEG_TEST_OPTS, self.input_file, codec, panopts, audio_track, subopts, output_file)
    execute_command(c)

  def tag(self, aud_list, sub_list, output_file):
    if not args.m:
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
        #if args.e:
        #  forc = 0 # Do not tag any subtitle as FORCED when dual audio is selected
        c = '%s "%s" --edit track:s%d --set flag-forced=%d'%(MKVPROPEDIT_BIN, output_file, n + 1, forc)
        execute_command(c)

  def remux_tracks(self, original_file, av_files, aud_list, sub_list, output_file):
    #global REMUX_MODE
    #if REMUX_MODE:
    #  print '* Remuxing to "%s"...'%(output_file)
    #  if self.extension == 'avi':
    #    track_files = ' -fflags +genpts '
    #  else:
    #    track_files = ''
    #  track_files += ' -i "%s" '%(original_file)
    #  for f in av_files:
    #    track_files += ' -i "%s" '%(f)
    #  extra_map = ''
    #  if len(av_files) > 1:
    #    extra_map += ' -map 2:a:0 '
    #  if not sub_list == []:
    #    extra_map += ' -map 1:s '
    #  c = '%s %s %s -threads 4 -y -c:v copy -c:a copy -c:s copy -map 0:v:0 -map 1:a:0 %s -f matroska -map_metadata -1 "%s"'%(FFMPEG_BIN, FFMPEG_TEST_OPTS, track_files, extra_map, output_file)
    #  execute_command(c)
    #  # Subtitle extraction to external files: ******
    #  if args.subext:
    #    print '* Extracting subtitles to external files...'
    #    print self.info.sub_languages
    #    for s in sub_list:
    #      output_sub_file = '%s.%s.srt'%(self.base_filename, language_code(self.info.sub_languages[s]))
    #      print 'Extracting subtitle track "%s" to file "%s"'%(s, output_sub_file)
    #      c = '%s -y -i "%s" -vn -an -c:s srt -map 0:s:%d "%s"'%(FFMPEG_BIN, self.input_file, s, output_sub_file)
    #      execute_command(c)
    #else:
    print '* Copying to "%s"...'%(output_file)
    if not args.z:
      shutil.copyfile(original_file, output_file)
    # Pre-tagging if MP4 output:
    if not args.k:
      self.tag(aud_list, sub_list, output_file)

# Subroutines:

def execute_command(c):
  if NICE_BIN != '':
    c = NICE_BIN + ' -n 19 ' + c
  print '> Executing: %s'%(c)
  if not args.z:
    os.system(c)

def clean_temp_files():
  print '* Cleaning temporary files...'
  try:
    os.remove(TEMP_REMUX_FILE)
    os.remove(TEMP_AV_FILE_0)
    os.remove(TEMP_AV_FILE_1)
  except:
    #  print '- Warning: error cleaning temporary files'
    pass
  return

#def image_variance(im)
#  h = []
#  for k in range(0, 256):
#    h.append(0)
#  for x in range(0, 320):
#    for y in range(0, 180):
#      r, g, b = im.getpixel((x, y))
#      cmin = min(r, g, b)
#      cmax = max(r, g, b)
#      l = (cmin + cmax)/2
#      h[l] += 1
#  m = float(sum(h))/256.0
#  v = float(0.0)
#  for k in range(0, 256):
#    v += (float(h[k]) - m)*(float(h[k]) - m)
#  v /= 256.0
#  return v

def thumbnail_quality(f):
  import Image
  im = Image.open(f)
  lum1 = 0
  lum2 = 0
  lum3 = 0
  for x in range(0, 104):
    for y in range(0, 180):
      r, g, b = im.getpixel((x, y))
      cmin = min(r, g, b)
      cmax = max(r, g, b)
      l = (cmin + cmax) / 2
      lum1 += l
  for x in range(105, 216):
    for y in range(0, 180):
      cmin = min(r, g, b)
      cmax = max(r, g, b)
      l = (cmin + cmax) / 2
      lum2 += l
  for x in range(216, 320):
    for y in range(0, 180):
      cmin = min(r, g, b)
      cmax = max(r, g, b)
      l = (cmin + cmax) / 2
      lum3 += l
  q = abs(2 * lum2 - (lum1 + lum3))
  im.close()
  return q

def generate_bif_file(f):

  v = MediaFile(f)

  if v.extension in VXT:
    if not args.g and not args.w and os.path.isfile(v.output_bif_file):
      print '* Destination file already exists (skipping)'
      return

  if not args.z:
    try:
      shutil.rmtree(TEMP_BIF_DIR)
    except:
      pass

  print '> Generating thumbnails...'

  if not args.z:
    os.mkdir(TEMP_BIF_DIR)
  #c = '%s -i "%s" -f image2 -r 1/10 -s 320x180 -ss 10.5 %s/%%08d.jpg'%(FFMPEG_BIN, v.input_file, TEMP_BIF_DIR)
  #c = '%s -i "%s" -f image2 -r 1/10 -s 320x180 -ss 0.5 %s/%%08d.jpg'%(FFMPEG_BIN, v.input_file, TEMP_BIF_DIR)
  c = '%s %s -i "%s" -f image2 -r 1/10 -s 320x180 %s/%%08d.jpg'%(FFMPEG_BIN, FFMPEG_TEST_OPTS, v.input_file, TEMP_BIF_DIR)
  execute_command(c)

  lis = os.listdir(TEMP_BIF_DIR)
  lis = sorted(lis)
  tot = len(lis)
  print '* Thumbnails generated: %d'%(tot)

  print '* Removing 1st thumbnail... ',
  if not args.z:
    try:
      os.remove('%s/00000001.jpg'%(TEMP_BIF_DIR))
      print 'OK'
    except:
      print 'ERROR'
  print '* Removing 2nd thumbnail... ',
  if not args.z:
    try:
      os.remove('%s/00000002.jpg'%(TEMP_BIF_DIR))
      print 'OK'
    except:
      print 'ERROR'
  k = 1
  while k <= tot - 2:
    tna = '%08d.jpg'%(k + 2)
    tnb = '%08d.jpg'%(k)
    print '* Renaming thumbnail %s to %s...'%(tna, tnb),
    if not args.z:
      try:
        os.rename('%s/%s'%(TEMP_BIF_DIR, tna), '%s/%s'%(TEMP_BIF_DIR, tnb))
        print 'OK'
      except:
        print 'ERROR'
    k += 1

  print '* Extracting thumbnail...'
  total_thumbs = len(os.listdir(TEMP_BIF_DIR))
  thumb = []
  for k in range(0, THUMB_POOL_SIZE):
    thumb.append(int(total_thumbs / 10) + k)
  thumbfile = []
  thumbquality = []
  print '- Total thumbnails = %d'%(total_thumbs)
  for t in thumb:
    f = '%s/%08d.jpg'%(TEMP_BIF_DIR, t)
    q = thumbnail_quality(f)
    thumbfile.append(f)
    thumbquality.append(q)
    print '- Thumbnail candidate: %s (quality = %g)'%(f, q)
  maxqfile = thumbfile[thumbquality.index(max(thumbquality))]
  print '- Thumbnail chosen = %s'%(maxqfile)
  if not args.z:
    try:
      os.nice(19)
      shutil.copyfile(maxqfile, '%s'%(v.output_jpg_file))
      print 'OK'
    except:
      print 'ERROR'

  print '* Compiling BIF file...'
  c = '%s -t 10000 %s'%(BIFTOOL_BIN, TEMP_BIF_DIR)
  execute_command(c)

  print '* Renaming BIF file...',
  if not args.z:
    try:
      #os.rename('%s.bif'%(TEMP_BIF_DIR), '%s.bif'%(v.base_filename))
      os.rename('%s.bif'%(TEMP_BIF_DIR), '%s'%(v.output_bif_file))
      print 'OK'
    except:
      print 'ERROR'
  if not args.z and not args.g:
    try:
      shutil.rmtree(TEMP_BIF_DIR)
    except:
      pass

def tagonly_video_file(f):
  v = MediaFile(f)
  c = '%s "%s" --edit info --set title="%s"'%(MKVPROPEDIT_BIN, v.input_file, v.movie_name)
  execute_command(c)

def transcode_video_file(f):

  if args.g and not args.z:
    clean_temp_files()

  v = MediaFile(f)

  if v.extension in VXT:
    if not args.g and not args.w and os.path.isfile(v.output_file):
      print '* Destination file already exists (skipping)'
      return

  # Audio/sub tracks processing:

  track_audio_eng = v.info.select_audio_track(ENGLISH)
  track_sub_eng_f = v.info.select_sub_track(ENGLISH, True)
  track_sub_eng_n = v.info.select_sub_track(ENGLISH, False)
  track_audio_spa = v.info.select_audio_track(SPANISH)
  track_sub_spa_f = v.info.select_sub_track(SPANISH, True)
  track_sub_spa_n = v.info.select_sub_track(SPANISH, False)

  track_audio_0 = -1
  track_audio_1 = -1
  DUAL = False
  if track_audio_spa >= 0:
    track_audio_0 = track_audio_spa
  else:
    if track_audio_eng >= 0:
      track_audio_0 = track_audio_eng
    else:
      track_audio_0 = 0
  if args.e:
    if track_audio_eng >= 0:
      track_audio_0 = track_audio_eng
      if track_audio_spa >= 0:
        DUAL = True
        track_audio_1 = track_audio_spa
  if args.a: # Audio track selected by user
    track_audio_0 = int(args.a[0])

  aud_list = [track_audio_0]
  if track_audio_1 >= 0:
    aud_list.append(track_audio_1)

  sub_list = []
  if not args.nosub: # --nosub = No subtitles
    if args.e:
      if track_sub_eng_f >= 0:
        sub_list.append(track_sub_eng_f)
      if track_sub_eng_n >= 0:
        sub_list.append(track_sub_eng_n)
    if track_sub_spa_f >= 0:
      sub_list.append(track_sub_spa_f)
    if track_sub_spa_n >= 0:
      sub_list.append(track_sub_spa_n)

  aud_list.sort()
  sub_list.sort()

  audio_track_files = []
  #if REMUX_MODE:
  #  if not DUAL:
  #    v.transcode_audio_track(track_audio_0, sub_list, TEMP_AV_FILE_0)
  #    audio_track_files = [TEMP_AV_FILE_0]
  #  else:
  #    v.transcode_audio_track(track_audio_0, sub_list, TEMP_AV_FILE_0)
  #    audio_track_files = [TEMP_AV_FILE_0]
  #    v.transcode_audio_track(track_audio_1, [], TEMP_AV_FILE_1)
  #    audio_track_files.append(TEMP_AV_FILE_1)

  # Video(/Audio) transcoding:
  if not args.k:
    # Track remuxing:
    v.remux_tracks(f, audio_track_files, aud_list, sub_list, TEMP_REMUX_FILE)
    v.transcode(TEMP_REMUX_FILE, aud_list, sub_list)
  else:
    v.transcode(f, aud_list, sub_list)

  # Post-tagging if MKV output:
  if args.k:
    v.tag(aud_list, sub_list, v.output_file)

  if not args.g and not args.z:
    clean_temp_files()

def process_directory(dir):
  lis = os.listdir(dir)
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
      if args.b:
        generate_bif_file(rut)
      else:
        if args.tagonly:
          tagonly_video_file(rut)
        else:
          transcode_video_file(rut)

def process_file(f):
  if args.b:
    generate_bif_file(f)
  else:
    if args.tagonly:
      tagonly_video_file(f)
    else:
      transcode_video_file(f)

def verify_software(b, critical):
  if not b == '':
    print 'Checking for %s...'%(b),
    if distutils.spawn.find_executable(b) is None:
      if critical:
        sys.exit('MISSING!')
      else:
        print 'MISSING! (WARNING)'
    else:
      print 'OK'

# Main routine:

verify_software(FFMPEG_BIN, True)
verify_software(HANDBRAKECLI_BIN, True)
verify_software(MEDIAINFO_BIN, True)
verify_software(MKVPROPEDIT_BIN, True)
verify_software(NICE_BIN, True)
#verify_software(SED_BIN, True)
verify_software(BIFTOOL_BIN, False)

if args.input:
  for f in args.input:
    process_file(f)
else:
  process_directory('.')
