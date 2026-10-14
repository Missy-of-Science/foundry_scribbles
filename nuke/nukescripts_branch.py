"modified nukescripts.branch fixing the connection error it causes"

import nukescripts
import nuke


def branch():
    "modified nukescripts function"
    selected_nodes = nuke.selectedNodes(recursive=True)
    if not selected_nodes:
        return

    this_group = selected_nodes[0].parent()
    if this_group is not nuke.root() and (this_group.locked() or this_group.subgraphLocked()):
        reason = "published" if this_group.subgraphLocked() else "locked"
        raise RuntimeError(f"Can't branch because {this_group.name()} is {reason}")

    top_node = None
    for i in selected_nodes:
        for j in range(i.inputs()):
            if not i.input(j).isSelected():
                if top_node is not None:
                    raise ValueError(
                        "You seem to have several branch-roots or unselected mask inputs."
                    )
                top_node = i.input(j)

    with this_group:
        nuke.nodeCopy(nukescripts.cut_paste_file())
        _ = [n.setSelected(False) for n in nuke.selectedNodes()]
        nuke.nodePaste(nukescripts.cut_paste_file())

    selected_nodes = nuke.selectedNodes(recursive=True)
    first_node_pasted = selected_nodes[-1]

    for i in selected_nodes:
        xpos = i.knob("xpos").value()
        i.knob("xpos").setValue(xpos + 80)

    if top_node is not None:
        first_node_pasted.setInput(0, top_node)


if __name__ == "__main__":
    menu = nuke.menu("Nuke").findItem("Edit")
    menu.addCommand("Branch", "branch()", shortcut="#B")
    # menu.addCommand("Branch", "nukescripts.branch()", shortcut="#B")
