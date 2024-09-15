""" Auto Frame Detect
based on the idea of Gabrielle Garam You
expected usecase: Nuke's CopyCat - identify frames with greatest difference
* user defined percentage of difference
* create a list of frames, that differ at least that much
* compare new frames to latest list element
* create TimeWarp and reduce Framerange to length of found frames"""

import os
import re

from Qt import QtWidgets
import cv2
import nuke

REFERENCE = None
THRESHOLD = 5
DETECT_THRESHOLD = 30


def detect_motion(current_frame):
    "detect difference between reference frame and current frame"
    # Calculate the absolute difference between frames
    frame_diff = cv2.absdiff(REFERENCE, current_frame)

    # Apply thresholding to highlight significant differences
    _, thresholded_diff = cv2.threshold(frame_diff, DETECT_THRESHOLD, 255, cv2.THRESH_BINARY)

    # Apply morphological operations to remove noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    opened_diff = cv2.morphologyEx(thresholded_diff, cv2.MORPH_OPEN, kernel)

    # Find contours of moving objects
    contours, _ = cv2.findContours(opened_diff, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Get bounding rectangles for the contours
    bounding_rects = [cv2.boundingRect(contour) for contour in contours]

    return bounding_rects


# Function to process each frame
def process_frame(frame, dimension):
    "create comparable object, show difference on screen and update reference frame if necessary"
    global REFERENCE
    current_frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if REFERENCE is None:
        REFERENCE = current_frame_gray
        return 0

    motion_regions = detect_motion(current_frame_gray)

    for region in motion_regions:
        x, y, w, h = region
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    cv2.imshow("Frame", frame)

    percentage = (sum([w * h for _, _, w, h in motion_regions]) / dimension) * 100

    if percentage > THRESHOLD:
        REFERENCE = current_frame_gray

    return percentage


def start_autodetection(readnode):
    "setup and prepare processing of VideoCapture object"
    dimension = readnode.width() * readnode.height()

    is_mov = readnode["file_type"].value() == "mov"

    # create context to change framenumber of imagesequences
    ctx = nuke.OutputContext()

    # Create a VideoCapture object
    cap = cv2.VideoCapture()
    if is_mov:
        cap.open(readnode["file"].value())

    percent = [[readnode["first"].value(), 0]]
    for frame_number in range(readnode["first"].value(), readnode["last"].value()):
        if not is_mov:
            ctx.setFrame(frame_number)
            cap.open(readnode["file"].toScript(False, ctx))
        success, frame = cap.read()

        if not success:
            print("Error reading frame")
            break

        difference = process_frame(frame, dimension)
        if difference >= THRESHOLD:
            percent.append([frame_number, difference])

        # Check if a key has been pressed
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    # Release resources and close the windows
    cap.release()
    cv2.destroyAllWindows()

    return percent


def create_timenode(frames, inputnode):
    "create timewarp and framerange nodes for found list of percentages"
    timewarp = nuke.nodes.TimeWarp()
    first = nuke.root().firstFrame()
    last = first + len(frames) - 1
    timewarp["lookup"].fromScript(f"{{curve K x{first} {' '.join([str(i[0]) for i in frames])}}}")

    timewarp.setXpos(inputnode.xpos())
    timewarp.setYpos(inputnode.ypos() + 102)
    timewarp.setInput(0, inputnode)
    timewarp.selectOnly()
    timewarp.autoplace()

    framerange = nuke.nodes.FrameRange()
    framerange["first_frame"].setValue(first)
    framerange["last_frame"].setValue(last)
    framerange["label"].setValue(f"{first}-{last} ({THRESHOLD}%/{DETECT_THRESHOLD})")

    framerange.setXpos(timewarp.xpos())
    framerange.setYpos(timewarp.ypos() + 24)
    framerange.setInput(0, timewarp)
    framerange.setSelected(True)
    framerange.autoplace()

    inputnode.dependent()  # otherwise viewer variable is empty
    viewer = [view for view in inputnode.dependent() if view.Class() == "Viewer"]
    for v in viewer:
        v.setInput(v.dependencies().index(inputnode), framerange)


def create_alternative_read(filename, width, height):
    "get read node files to process OpenCV - if jpg files exist in the same way the exr do"

    # first full res
    tmp_file = re.sub("exr", "jpg", filename)
    tmp_files = [n for n in os.listdir(os.path.dirname(tmp_file)) if n.endswith("jpg")]
    if tmp_files:
        return tmp_file

    # second half res - based on internal naming convention, check for resolution proxy
    half_file = re.sub(f"{width}x{height}", f"{int(width/2)}x{int(height/2)}", tmp_file)
    try:
        tmp_files = [n for n in os.listdir(os.path.dirname(half_file)) if n.endswith("jpg")]
    except FileNotFoundError:
        pass
    else:
        if tmp_files:
            return half_file

    # last editorial - based on internal naming convention, check for HD editorial proxy
    editorial_file = re.sub(f"{width}x{height}_jpg", "1920x1080_jpg-editorial", tmp_file)
    tmp_files = [n for n in os.listdir(os.path.dirname(editorial_file)) if n.endswith("jpg")]
    if tmp_files:
        return editorial_file

    # all if clauses failed, hence no file was found
    raise FileNotFoundError("No alternative jpg files found!")


def ask_processing(redo=False):
    "function to start from within Nuke"
    global THRESHOLD
    global REFERENCE
    global DETECT_THRESHOLD

    try:
        n = nuke.selectedNode()
        if not n.Class() == "Read":
            raise ValueError("Please select a ReadNode.")
    except ValueError as err:
        nuke.message(str(err))
        return

    if n["file_type"].value() == "exr":
        try:
            tmp_file = create_alternative_read(n["file"].value(), int(n.width()), int(n.height()))
        except FileNotFoundError as err:
            QtWidgets.QMessageBox.critical(None, "Error", str(err))
            return
        n.selectOnly()
        nuke.duplicateSelectedNodes()
        n = nuke.selectedNode()
        n.setXpos(n.xpos() + 100)
        n.autoplace()
        n["file"].setValue(tmp_file)

    if not redo:
        c = QtWidgets.QInputDialog.getInt(None, "Threshold", "Percent Threshold", THRESHOLD, 0, 100)

        if not c[1]:
            return

        THRESHOLD = c[0]

    frame_indices = start_autodetection(n)
    REFERENCE = None

    question = f"Found {len(frame_indices)} frames with more than {THRESHOLD}% difference."
    ask = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Question, "Title", question)
    ask.setToolTip(
        "You have the option to change the Percentage Threshold immediatly and recalculate the "
        + "frames.\n\nAdditionally you can change the threshold OpenCV uses to detect the "
        + "difference between the\nframes. It is set to 30 by default and will be reset at "
        + "cancellation or TimeWarp creation!"
    )
    ask.addButton("Create TimeWarp", QtWidgets.QMessageBox.ActionRole)
    ask.addButton("Change Percentage", QtWidgets.QMessageBox.ActionRole)
    ask.addButton("Change Detection Threshold", QtWidgets.QMessageBox.ActionRole)
    ask.addButton(QtWidgets.QMessageBox.Cancel)
    ask.setDefaultButton(QtWidgets.QMessageBox.Ok)

    res = ask.exec_()

    if res == 2:
        d = QtWidgets.QInputDialog.getInt(
            None, "Threshold", "Detection Threshold", DETECT_THRESHOLD
        )
        if d[1]:
            DETECT_THRESHOLD = d[0]
            ask_processing(True)
            return

    elif res == 1:
        ask_processing()
        return

    elif res == 0:
        print(frame_indices)
        create_timenode(frame_indices, n)

    DETECT_THRESHOLD = 30


if __name__ == "__main__":
    ask_processing()
