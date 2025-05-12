# Created by DarkTrick - Modified by ChatGPT for robustness

import subprocess
import tempfile
import sys
import os
import logging

# ===========================
# ==== Configure logging ====
# ===========================
log_level = logging.ERROR
log_filename = 'silence_cutter.log'
logger = logging.getLogger('')
logger.setLevel(log_level)
log_handler = logging.FileHandler(log_filename, delay=True)
logger.addHandler(log_handler)


def findSilences(filename, dB=-35):
    """
    Returns a list of timestamps where silence starts and ends:
        [start1, end1, start2, end2, ...]
    """
    logging.debug(f"findSilences() - filename = {filename}, dB = {dB}")

    command = [
        "ffmpeg", "-i", filename,
        "-af", f"silencedetect=n={dB}dB:d=1",
        "-f", "null", "-"
    ]
    output = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    s = output.stderr.decode("utf-8")  # Use stderr where silencedetect output goes
    lines = s.splitlines()
    time_list = []

    for line in lines:
        if "silencedetect" in line:
            if "silence_start" in line:
                try:
                    time_str = line.split("silence_start:")[-1].strip()
                    time_list.append(float(time_str))
                except ValueError:
                    logging.error(f"Could not parse silence_start in line: {line}")
            elif "silence_end" in line:
                try:
                    time_str = line.split("silence_end:")[-1].split()[0].strip()
                    time_list.append(float(time_str))
                except ValueError:
                    logging.error(f"Could not parse silence_end in line: {line}")

    return time_list


def getVideoDuration(filename: str) -> float:
    logging.debug(f"getVideoDuration() - filename = {filename}")

    command = [
        "ffprobe", "-i", filename, "-v", "quiet",
        "-show_entries", "format=duration",
        "-hide_banner", "-of", "default=noprint_wrappers=1:nokey=1"
    ]
    output = subprocess.run(command, stdout=subprocess.PIPE)
    s = output.stdout.decode("utf-8").strip()
    try:
        return float(s)
    except ValueError:
        logging.error(f"Failed to parse video duration: {s}")
        return 0.0


def getSectionsOfNewVideo(silences, duration):
    return [0.0] + silences + [duration]


def ffmpeg_filter_getSegmentFilter(videoSectionTimings):
    ret = ""
    for i in range(int(len(videoSectionTimings) / 2)):
        start = videoSectionTimings[2 * i]
        end = videoSectionTimings[2 * i + 1]
        ret += f"between(t,{start},{end})+"
    return ret[:-1]  # Remove trailing '+'


def getFileContent_videoFilter(videoSectionTimings):
    return f"select='{ffmpeg_filter_getSegmentFilter(videoSectionTimings)}', setpts=N/FRAME_RATE/TB"


def getFileContent_audioFilter(videoSectionTimings):
    return f"aselect='{ffmpeg_filter_getSegmentFilter(videoSectionTimings)}', asetpts=N/SR/TB"


def writeFile(filename, content):
    with open(filename, "w") as file:
        file.write(str(content))


def ffmpeg_run(file, videoFilter, audioFilter, outfile):
    vFile = tempfile.NamedTemporaryFile(mode="w", encoding="UTF-8", prefix="silence_video", delete=False)
    aFile = tempfile.NamedTemporaryFile(mode="w", encoding="UTF-8", prefix="silence_audio", delete=False)

    writeFile(vFile.name, videoFilter)
    writeFile(aFile.name, audioFilter)

    command = [
        "ffmpeg", "-i", file,
        "-filter_script:v", vFile.name,
        "-filter_script:a", aFile.name,
        outfile
    ]
    subprocess.run(command)

    vFile.close()
    aFile.close()


def cut_silences(infile, outfile, dB=-35):
    print("Detecting silences...")
    silences = findSilences(infile, dB)
    duration = getVideoDuration(infile)
    videoSegments = getSectionsOfNewVideo(silences, duration)

    videoFilter = getFileContent_videoFilter(videoSegments)
    audioFilter = getFileContent_audioFilter(videoSegments)

    print("Creating new video...")
    ffmpeg_run(infile, videoFilter, audioFilter, outfile)


def printHelp():
    print("Usage:")
    print("   silence_cutter.py [infile] [optional: outfile] [optional: dB]")
    print("\nDefaults:")
    print("   [outfile] = [infile]_cut")
    print("   [dB] = -30")
    print("      Lower dB = more sensitive to silence")
    print("\nDependencies:")
    print("   ffmpeg")
    print("   ffprobe")


def main():
    args = sys.argv[1:]

    if not args or args[0] == "--help":
        printHelp()
        return

    infile = args[0]
    if not os.path.isfile(infile):
        print(f"ERROR: The infile could not be found:\n{infile}")
        return

    outfile = os.path.splitext(infile)[0] + "_cut" + os.path.splitext(infile)[1]
    dB = -30

    if len(args) >= 2:
        outfile = args[1]

    if len(args) >= 3:
        try:
            dB = float(args[2])
        except ValueError:
            print(f"ERROR: Invalid dB value: {args[2]}")
            return

    cut_silences(infile, outfile, dB)


if __name__ == "__main__":
    main()
