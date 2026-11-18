import sys, zipfile, xml.etree.ElementTree as ET
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
root = ET.fromstring(zipfile.ZipFile(sys.argv[1]).read("word/document.xml"))
def txt(e): return "".join(t.text or "" for t in e.iter(W + "t")).strip()
body = root.find(W + "body")
for el in body:
    if el.tag == W + "p":
        x = txt(el)
        if x: print(x)
    elif el.tag == W + "tbl":
        print("=== TABLA")
        for r in el.iter(W + "tr"):
            cs = []
            for c in r.findall(W + "tc"):
                x = " / ".join(txt(p) for p in c.iter(W + "p") if txt(p))
                if not cs or cs[-1] != x: cs.append(x)
            print(" | ".join(cs))
