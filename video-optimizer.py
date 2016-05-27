#!/usr/bin/python

# Imports:

import os, string, argparse, subprocess, distutils.spawn, sys

# Constants:

VXT = ['mkv', 'mp4', 'm4v', 'mov', 'mpg', 'mpeg', 'avi', 'vob', 'mts', 'm2ts', 'wmv']
TEST_TIME = 300 # 300 seg = 5 min
VIDEO_QUALITY = 22
VIDEO_QUALITY_HD = 18
SPANISH = 'Spanish'
ENGLISH = 'English'
TEMP_REMUX_FILE = 'temprmux.mkv'
TEMP_AV_FILE_0 = 'tempav00.mkv'
TEMP_AV_FILE_1 = 'tempav01.mkv'

if os.name == 'posix':
  FFMPEG_BIN = 'ffmpeg'
  HANDBRAKECLI_BIN = 'HandBrakeCLI'
  MEDIAINFO_BIN = 'mediainfo'
  MKVPROPEDIT_BIN = 'mkvpropedit'
  NICE_BIN = 'nice'
  SED_BIN = 'sed'
else:
  BIN_PATH = 'C:/script/bin/'
  FFMPEG_BIN = '%sffmpeg.exe'%(BIN_PATH)
  HANDBRAKECLI_BIN = '%sHandBrakeCLI.exe'%(BIN_PATH)
  MEDIAINFO_BIN = '%sMediaInfo.exe'%(BIN_PATH)
  MKVPROPEDIT_BIN = '%smkvpropedit.exe'%(BIN_PATH)
  NICE_BIN = ''
  SED_BIN = '%ssed.exe'%(BIN_PATH)

# Options:

parser = argparse.ArgumentParser(description = 'Video transcoder/processor (v4.0.2)')
#parser.add_argument('-a', nargs = 1, help = 'audio track (1 by default)')
parser.add_argument('-b', action = 'store_true', help = 'Debug mode')
parser.add_argument('-e', action = 'store_true', help = 'English + Spanish (Dual audio/subtitles)')
parser.add_argument('-d', action = 'store_true', help = 'Dolby surround 3.1 audio output [BETA]')
parser.add_argument('-f', action = 'store_true', help = 'Full HD output (high quality)')
parser.add_argument('-k', action = 'store_true', help = 'Matroska (MKV) output')
parser.add_argument('-m', action = 'store_true', help = 'Skip adding metadata')
parser.add_argument('-o', nargs = 1, help = 'Output path')
parser.add_argument('-q', nargs = 1, help = 'Quality factor (%d by default)'%(VIDEO_QUALITY))
parser.add_argument('-r', action = 'store_true', help = 'Rebuild original folder structure')
#parser.add_argument('-s', nargs = 1, help = 'Subtitle track (spanish forced searched by default / 0 disables subs)')
parser.add_argument('-t', action = 'store_true', help = 'Test mode (only the first %d s of video are processed)'%(TEST_TIME))
parser.add_argument('-v', action = 'store_true', help = 'Central speaker (voice) boost [BETA]')
parser.add_argument('-w', action = 'store_true', help = 'Overwrite existing files (skip by default)')
parser.add_argument('-x', action = 'store_true', help = 'X265 codec (BETA)')
parser.add_argument('-z', action = 'store_true', help = 'dry run')
parser.add_argument('input', nargs='*', help = 'input file(s) (if missing process all video files)')
args = parser.parse_args()

FFMPEG_TEST_OPTS = ''
HANDBRAKE_TEST_OPTS = ''
if args.t:
  FFMPEG_TEST_OPTS = ' -t %d '%(TEST_TIME)
  HANDBRAKE_TEST_OPTS = ' --stop-at duration:%s '%(TEST_TIME)

# Classes:

class MediaInfo:

  def __init__(self):
    self.audio_codec = []
    self.audio_languages = []
    self.audio_channels = []
    self.audio_descriptions = []
    self.sub_languages = []
    self.sub_forced = []

  def audio_tracks_count(self):
    return len(self.audio_languages)

  def sub_tracks_count(self):
    return len(self.sub_languages)

  def print_info(self):
    print '* Media info found:'
    for t in range(0, self.audio_tracks_count()):
      print ('- Audio track %d: Codec = %s, Language = %s, Channels = %d, Audio Description = %s'%(t, self.audio_codec[t], self.audio_languages[t], self.audio_channels[t], self.audio_descriptions[t]))
    for t in range(0, self.sub_tracks_count()):
      print ('- Subtitle track %d: Language = %s, Forced = %s'%(t, self.sub_languages[t], self.sub_forced[t]))

  def select_audio_track(self, l):
    print '* Searching for %s audio track...'%(l)
    r = 0
    for i in range(0, self.audio_tracks_count()):
      if not self.audio_descriptions[i] and self.audio_languages[i] == l:
        if (args.d and self.audio_channels[i] == 6 or not args.d and self.audio_channels[i] == 2):
          r = i
    for i in range(0, self.audio_tracks_count()):
      if not self.audio_descriptions[i] and self.audio_languages[i] == l:
        r = i
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
    self.output_file = n
    if args.f:
      self.output_file += '[HQ]'
    if args.x:
      self.output_file += '[X265]'
    if args.q:
      self.output_file += '[Q%s].mp4'%(args.q[0])
    if args.k:
      self.output_file += '[OV].mkv'
    else:
      self.output_file += '[OV].mp4'
    # Movie name:
    self.movie_name = n.split(' [')[0]

    # Media info extraction
    self.info = MediaInfo()
    if self.extension == 'mkv':
      print '> Extracting file media info...'
      # Audio tracks count
      o = subprocess.check_output('%s --Inform="General;%%AudioCount%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      audcnt = int(o)
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
        self.info.audio_languages.append(o[i])
      # Audio Channels
      o = subprocess.check_output('%s --Inform="Audio;%%Channel(s)%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
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
        if 'descri' in s[t].lower():
          self.info.audio_descriptions.append(True)
        else:
          self.info.audio_descriptions.append(False)
      # Subtitle tracks count
      o = subprocess.check_output('%s --Inform="General;%%TextCount%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      subcnt = int(o)
      print '- Subtitle tracks found = %d'%(subcnt)
      # Subtitle languages
      o = subprocess.check_output('%s --Inform="General;%%Text_Language_List%%" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      o = o.split(' / ')
      self.info.sub_languages = o
      # Subtitle forced
      o = subprocess.check_output('%s --Inform="Text;%%Forced%%/" "%s"'%(MEDIAINFO_BIN, self.input_file), shell=True)
      o = o.rstrip()
      o = o.split('/')
      self.info_sub_forced = []
      for i in range(0, len(o) - 1):
        if o[i] == 'Yes':
          self.info.sub_forced.append(True)
        else:
          self.info.sub_forced.append(False)
      self.info.print_info()

  def transcode(self, input_file):
    print '* Transcoding media file "%s" to "%s"...'%(input_file, self.output_file)
    options = ' --preset="Normal" --loose-anamorphic '
    if args.x:
      options += ' --encoder x265 '
    if not args.f:
      options += ' --maxWidth 1280 '
    if args.q:
      quantizer = int(args.q[0])
    else:
      if args.f:
        quantizer = VIDEO_QUALITY_HD
      else:
        quantizer = VIDEO_QUALITY
    if args.x:
      quantizer = quantizer + 1
    options += ' --quality %d '%(quantizer)
    if args.e:
      audopts = '--audio 1,2'
    else:
      audopts = '--audio 1'
    if args.d or args.v:
      audopts += ' --aencoder copy'
    else:
      audopts += ' --mixdown stereo --drc 2.0'
    c = '%s %s -i "%s" --optimize --large-file --markers %s %s --subtitle 1,2,3,4 -o "%s"'%(HANDBRAKECLI_BIN, HANDBRAKE_TEST_OPTS, input_file, options, audopts, self.output_file)
    execute_command(c)

  def transcode_audio_track(self, audio_track, sub_tracks, output_file):
    print '* Transcoding audio track %d to "%s"'%(audio_track, output_file)
    if self.info.audio_channels == []:
      codec = 'copy'
      panopts = ''
    else:
      if self.info.audio_channels[audio_track] == 2: # Stereo source
        if args.v:
          codec = 'libfaac'
          panopts = '-af "pan=stereo|c0<0.5*c0+0.5*c3+c1+0.5*c5|c1<0.5*c2+0.5*c4+c1+0.5*c5"'
        else:
          codec = 'copy'
          panopts = ''
      else: # Surround source
        if args.d:
          codec = 'ac3'
          panopts = '-af "pan=3.1|c0<0.5*c0+0.5*c3|c1<c1|c2<0.5*c2+0.5*c4|c3<c5"'
        else:
          if args.v:
            codec = 'libfaac'
            panopts = '-af "pan=stereo|c0<0.5*c0+0.5*c3+c1+0.5*c5|c1<0.5*c2+0.5*c4+c1+0.5*c5"'
          else:
            codec = 'copy'
            panopts = ''
    if len(sub_tracks) > 0:
      subopts = ' -c:s copy '
      for i in range(0, len(sub_tracks)):
        subopts += ' -map 0:s:%d '%(sub_tracks[i])
    else:
      subopts = ''
    c = '%s %s -threads 4 -y -i "%s" -vn -map 0:a:%d -c:a %s %s %s -f matroska "%s"'%(FFMPEG_BIN, FFMPEG_TEST_OPTS, self.input_file, audio_track, codec, panopts, subopts, output_file)
    execute_command(c)

  def tag(self, sub_tracks_languages, sub_tracks_forced, output_file):
    if not args.m:
      c = '%s "%s" --edit info --set title="%s"'%(MKVPROPEDIT_BIN, output_file, self.movie_name)
      execute_command(c)
      if not args.e:
        c = '%s "%s" --edit track:a1 --set name="Spanish Default"'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
        c = '%s "%s" --edit track:a1 --set language=spa'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
        c = '%s "%s" --edit track:a1 --set flag-default=1'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
        c = '%s "%s" --edit track:a1 --set flag-forced=1'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
      else:
        c = '%s "%s" --edit track:a1 --set name="English Default"'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
        c = '%s "%s" --edit track:a1 --set language=eng'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
        c = '%s "%s" --edit track:a1 --set flag-default=1'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
        c = '%s "%s" --edit track:a1 --set flag-forced=1'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
        c = '%s "%s" --edit track:a2 --set name="Spanish"'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
        c = '%s "%s" --edit track:a2 --set language=spa'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
        c = '%s "%s" --edit track:a2 --set flag-default=0'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
        c = '%s "%s" --edit track:a2 --set flag-forced=0'%(MKVPROPEDIT_BIN, output_file)
        execute_command(c)
      for i in range(0, len(sub_tracks_languages)):
        l = sub_tracks_languages[i]
        if l == SPANISH:
          l = 'spa'
        else:
          if l == ENGLISH:
            l = 'eng'
        d = 0
        if i == 0:
          d = 1
        f = 0
        if sub_tracks_forced[i]:
          f = 1
        subtrackname = 'Other'
        if l == 'spa':
          subtrackname = 'Spanish'
        else:
          if l == 'eng':
            subtrackname = 'English'
        if f == 1:
          subtrackname = subtrackname + ' Forced'
        c = '%s "%s" --edit track:s%d --set name="%s"'%(MKVPROPEDIT_BIN, output_file, i + 1, subtrackname)
        execute_command(c)
        c = '%s "%s" --edit track:s%d --set language=%s'%(MKVPROPEDIT_BIN, output_file, i + 1, l)
        execute_command(c)
        c = '%s "%s" --edit track:s%d --set flag-default=%d'%(MKVPROPEDIT_BIN, output_file, i + 1, d)
        execute_command(c)
        c = '%s "%s" --edit track:s%d --set flag-forced=%d'%(MKVPROPEDIT_BIN, output_file, i + 1, f)
        execute_command(c)

  def remux_tracks(self, original_file, av_files, sub_tracks_languages, sub_tracks_forced, output_file):
    print '* Remuxing to "%s"...'%(output_file)
    if self.extension == 'avi':
      track_files = ' -fflags +genpts '
    else:
      track_files = ''
    track_files += ' -i "%s" '%(original_file)
    for f in av_files:
      track_files += ' -i "%s" '%(f)
    extra_map = ''
    if len(av_files) > 1:
      extra_map += ' -map 2:a:0 '
    if len(av_files) > 1 and not sub_tracks_languages == []:
      extra_map += ' -map 2:s '
    if not sub_tracks_languages == []:
      extra_map += ' -map 1:s '
    c = '%s %s %s -threads 4 -y -c:v copy -map 0:v:0 -c:a copy -c:s copy -map 1:a:0 %s -f matroska -map_metadata -1 "%s"'%(FFMPEG_BIN, FFMPEG_TEST_OPTS, track_files, extra_map, output_file)
    execute_command(c)
    # Pre-tagging if MP4 output:
    if not args.k:
      self.tag(sub_tracks_languages, sub_tracks_forced, output_file)

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
  #except:
  #  print '- Warning: error cleaning temporary files'
  return

def process_file(f):

  if args.b and not args.z:
    clean_temp_files()

  v = MediaFile(f)

  if v.extension in VXT:
    if not args.b and not args.w and os.path.isfile(v.output_file):
      print '* Destination file already exists (skipping)'
      return

  # Audio/sub tracks processing:
  if args.e: # English + Spanish audio output
    track_audio_0 = v.info.select_audio_track(ENGLISH)
    track_audio_1 = v.info.select_audio_track(SPANISH)
    track_sub_0 = v.info.select_sub_track(ENGLISH, True)
    track_sub_1 = v.info.select_sub_track(ENGLISH, False)
    track_sub_2 = v.info.select_sub_track(SPANISH, True)
    track_sub_3 = v.info.select_sub_track(SPANISH, False)
  else:
    track_audio_0 = v.info.select_audio_track(SPANISH)
    track_audio_1 = None
    track_sub_0 = v.info.select_sub_track(SPANISH, True)
    track_sub_1 = v.info.select_sub_track(SPANISH, False)
    track_sub_2 = -1
    track_sub_3 = -1
  sub_tracks_languages = []
  sub_tracks_forced = []
  sub_tracks_0 = []
  if track_sub_0 >= 0:
    sub_tracks_0.append(track_sub_0)
    if args.e:
      sub_tracks_languages.append(ENGLISH)
    else:
      sub_tracks_languages.append(SPANISH)
    sub_tracks_forced.append(True)
  if track_sub_1 >= 0:
    sub_tracks_0.append(track_sub_1)
    if args.e:
      sub_tracks_languages.append(ENGLISH)
    else:
      sub_tracks_languages.append(SPANISH)
    sub_tracks_forced.append(False)
  sub_tracks_1 = []
  if track_sub_2 >= 0:
    sub_tracks_1.append(track_sub_2)
    sub_tracks_languages.append(SPANISH)
    sub_tracks_forced.append(True)
  if track_sub_3 >= 0:
    sub_tracks_1.append(track_sub_3)
    sub_tracks_languages.append(SPANISH)
    sub_tracks_forced.append(False)
  print '* Subtitle track selected:'
  print sub_tracks_languages
  print sub_tracks_forced
  v.transcode_audio_track(track_audio_0, sub_tracks_0, TEMP_AV_FILE_0)
  audio_track_files = [TEMP_AV_FILE_0]
  if args.e: # English + Spanish audio output
    v.transcode_audio_track(track_audio_1, sub_tracks_1, TEMP_AV_FILE_1)
    audio_track_files.append(TEMP_AV_FILE_1)

  # Track remuxing:
  #v.remux_tracks(TEMP_REMUX_FILE, audio_track_files)
  v.remux_tracks(f, audio_track_files, sub_tracks_languages, sub_tracks_forced, TEMP_REMUX_FILE)

  # Video(/Audio) transcoding:
  v.transcode(TEMP_REMUX_FILE)

  # Post-tagging if MKV output:
  if args.k:
    v.tag(sub_tracks_languages, sub_tracks_forced, v.output_file)

  if not args.b and not args.z:
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
      process_file(rut)

def verify_software(b):
  if not b == '':
    print "Checking for %s..."%(b),
    if distutils.spawn.find_executable(b) is None:
      sys.exit("MISSING!")
    print "OK"

# Main routine:

verify_software(FFMPEG_BIN)
verify_software(HANDBRAKECLI_BIN)
verify_software(MEDIAINFO_BIN)
verify_software(MKVPROPEDIT_BIN)
verify_software(NICE_BIN)
#verify_software(SED_BIN)

if args.input:
  for f in args.input:
    process_file(f)
else:
  process_directory('.')
