' Helpers shared by MainScene and DetailsView for building RowList content.

function loadCatalog() as object
    return ParseJson(ReadAsciiFile("pkg:/data/catalog.json"))
end function

' Adds one artwork tile to a row ContentNode.
function addTile(row as object, poster as string, fields as object) as object
    node = row.createChild("ContentNode")
    node.HDPosterUrl = poster
    base = { titleId: "", label: "", subLabel: "", rank: 0, progress: 0.0, episode: 0, action: "open", url: "", playTitle: "" }
    base.append(fields)
    node.addFields(base)
    return node
end function

function metaLine(t as object) as string
    return t.genre + "  ·  " + t.year.ToStr() + "  ·  " + t.rating + "  ·  " + t.length
end function
