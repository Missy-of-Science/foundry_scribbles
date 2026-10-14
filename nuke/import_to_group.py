"import script into a group to keep the tree clean"

import os
import nuke


def import_to_group(s=None):
    "nukescripts.import_script() with modifications"
    if nuke.env["nc"]:
        spec = "*.nk; *.nknc; *.gizmo; *.gznc"
    elif nuke.env["indie"]:
        spec = "*.nk; *.nkind; *.gizmo; *.gzind"
    else:
        spec = "*.nk; *.gizmo"

    if s is None:
        s = nuke.getFilename("Import Script", spec, "", "script")
        if s is None:
            return

    group = nuke.createNode("Group")
    group["label"].setValue(os.path.basename(s))
    with group:
        try:
            nuke.nodePaste(s)
        except Exception as err:
            nuke.message(str(err))

        upper = nuke.selectedNode()
        lower = nuke.selectedNode()
        for sn in nuke.selectedNodes():
            if upper.ypos() > sn.ypos():
                upper = sn
            if lower.ypos() < sn.ypos():
                lower = sn

        i = nuke.nodes.Input()
        i.setXYpos(upper.xpos(), upper.ypos() - 50)

        o = nuke.nodes.Output()
        o.setXYpos(lower.xpos(), lower.ypos() + 50)


if __name__ == "__main__":
    import_to_group()
