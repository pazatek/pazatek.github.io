"""Writes RoomCoach.xcodeproj/project.pbxproj: the app plus its Live Activity widget extension.

Run after adding or removing a .swift file:  python3 gen_project.py
App/*.swift go in the app, Widget/*.swift in the extension, Shared/*.swift in both.
Set the Apple team with TEAM below (not secret) or pass DEVELOPMENT_TEAM=... to xcodebuild.
"""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = "com.piotrzatek.roomcoach"
TEAM = ""
IOS = "17.2"  # push-to-start needs 17.2


def oid(*parts):
    return hashlib.md5("/".join(parts).encode()).hexdigest()[:24].upper()


def swift(folder):
    return sorted(p.name for p in (HERE / folder).glob("*.swift"))


groups = {g: swift(g) for g in ("App", "Widget", "Shared")}
targets = {
    "RoomCoach": {"folders": ["App", "Shared"], "product": "RoomCoach.app", "ptype": "com.apple.product-type.application", "ftype": "wrapper.application"},
    "RoomWidget": {"folders": ["Widget", "Shared"], "product": "RoomWidget.appex", "ptype": "com.apple.product-type.app-extension", "ftype": "wrapper.app-extension"},
}
o = []  # (section, id, body)


def add(section, i, body):
    o.append((section, i, body))


def q(s):
    return s if s.replace("_", "").replace(".", "").replace("/", "").isalnum() and s else '"' + s.replace('"', '\\"') + '"'


def settings(d):
    return "{\n" + "".join(f"\t\t\t\t{k} = {q(v) if isinstance(v, str) else v};\n" for k, v in sorted(d.items())) + "\t\t\t}"


# files and groups
group_ids = []
for g, files in groups.items():
    kids = []
    for f in files:
        fid = oid("file", g, f)
        add("PBXFileReference", fid, f"{{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {q(f)}; sourceTree = \"<group>\"; }}")
        kids.append(fid)
    gid = oid("group", g)
    add("PBXGroup", gid, "{isa = PBXGroup; children = (" + ", ".join(kids) + f"); path = {g}; sourceTree = \"<group>\"; }}")
    group_ids.append(gid)
cfg_kids = []
for f, t in (("App-Info.plist", "text.plist.xml"), ("Widget-Info.plist", "text.plist.xml"), ("App.entitlements", "text.plist.entitlements")):
    fid = oid("file", "Config", f)
    add("PBXFileReference", fid, f"{{isa = PBXFileReference; lastKnownFileType = {t}; path = {q(f)}; sourceTree = \"<group>\"; }}")
    cfg_kids.append(fid)
add("PBXGroup", oid("group", "Config"), "{isa = PBXGroup; children = (" + ", ".join(cfg_kids) + "); path = Config; sourceTree = \"<group>\"; }")
group_ids.append(oid("group", "Config"))
prod_ids = []
for t, d in targets.items():
    pid = oid("product", t)
    add("PBXFileReference", pid, f"{{isa = PBXFileReference; explicitFileType = {q(d['ftype'])}; includeInIndex = 0; path = {q(d['product'])}; sourceTree = BUILT_PRODUCTS_DIR; }}")
    prod_ids.append(pid)
add("PBXGroup", oid("group", "Products"), "{isa = PBXGroup; children = (" + ", ".join(prod_ids) + "); name = Products; sourceTree = \"<group>\"; }")
main_group = oid("group", "main")
add("PBXGroup", main_group, "{isa = PBXGroup; children = (" + ", ".join(group_ids + [oid("group", "Products")]) + "); sourceTree = \"<group>\"; }")

common = {
    "SWIFT_VERSION": "5.0", "IPHONEOS_DEPLOYMENT_TARGET": IOS, "TARGETED_DEVICE_FAMILY": "1", "CODE_SIGN_STYLE": "Automatic",
    "DEVELOPMENT_TEAM": TEAM, "MARKETING_VERSION": "1.0", "CURRENT_PROJECT_VERSION": "1", "GENERATE_INFOPLIST_FILE": "YES",
    "INFOPLIST_KEY_CFBundleDisplayName": "Room", "SWIFT_EMIT_LOC_STRINGS": "YES",
}
per = {
    "RoomCoach": {
        "PRODUCT_BUNDLE_IDENTIFIER": BUNDLE, "PRODUCT_NAME": "$(TARGET_NAME)", "INFOPLIST_FILE": "Config/App-Info.plist",
        "CODE_SIGN_ENTITLEMENTS": "Config/App.entitlements", "INFOPLIST_KEY_UILaunchScreen_Generation": "YES",
        "INFOPLIST_KEY_UIApplicationSceneManifest_Generation": "YES", "INFOPLIST_KEY_UISupportedInterfaceOrientations": "UIInterfaceOrientationPortrait",
        "LD_RUNPATH_SEARCH_PATHS": "$(inherited) @executable_path/Frameworks",
    },
    "RoomWidget": {
        "PRODUCT_BUNDLE_IDENTIFIER": BUNDLE + ".widget", "PRODUCT_NAME": "$(TARGET_NAME)", "INFOPLIST_FILE": "Config/Widget-Info.plist",
        "SKIP_INSTALL": "YES", "APPLICATION_EXTENSION_API_ONLY": "YES",
        "LD_RUNPATH_SEARCH_PATHS": "$(inherited) @executable_path/Frameworks @executable_path/../../Frameworks",
    },
}
project_cfg = {
    "Debug": {"ALWAYS_SEARCH_USER_PATHS": "NO", "CLANG_ENABLE_MODULES": "YES", "DEBUG_INFORMATION_FORMAT": "dwarf", "ENABLE_TESTABILITY": "YES",
              "GCC_OPTIMIZATION_LEVEL": "0", "ONLY_ACTIVE_ARCH": "YES", "SDKROOT": "iphoneos", "SWIFT_ACTIVE_COMPILATION_CONDITIONS": "DEBUG $(inherited)",
              "SWIFT_OPTIMIZATION_LEVEL": "-Onone", "IPHONEOS_DEPLOYMENT_TARGET": IOS},
    "Release": {"ALWAYS_SEARCH_USER_PATHS": "NO", "CLANG_ENABLE_MODULES": "YES", "DEBUG_INFORMATION_FORMAT": "dwarf-with-dsym", "SDKROOT": "iphoneos",
                "SWIFT_COMPILATION_MODE": "wholemodule", "SWIFT_OPTIMIZATION_LEVEL": "-O", "VALIDATE_PRODUCT": "YES", "IPHONEOS_DEPLOYMENT_TARGET": IOS},
}


def cfg_list(owner, cfgs):
    ids = []
    for name, s in cfgs.items():
        cid = oid("cfg", owner, name)
        add("XCBuildConfiguration", cid, f"{{isa = XCBuildConfiguration; buildSettings = {settings(s)}; name = {name}; }}")
        ids.append(cid)
    lid = oid("cfglist", owner)
    add("XCConfigurationList", lid, "{isa = XCConfigurationList; buildConfigurations = (" + ", ".join(ids) + "); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release; }")
    return lid


target_ids = {}
for t, d in targets.items():
    bfs = []
    for g in d["folders"]:
        for f in groups[g]:
            bid = oid("build", t, g, f)
            add("PBXBuildFile", bid, f"{{isa = PBXBuildFile; fileRef = {oid('file', g, f)}; }}")
            bfs.append(bid)
    phases = [oid("sources", t), oid("frameworks", t), oid("resources", t)]
    add("PBXSourcesBuildPhase", phases[0], "{isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = (" + ", ".join(bfs) + "); runOnlyForDeploymentPostprocessing = 0; }")
    add("PBXFrameworksBuildPhase", phases[1], "{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }")
    add("PBXResourcesBuildPhase", phases[2], "{isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }")
    deps = []
    if t == "RoomCoach":
        embed_bf = oid("embedbf")
        add("PBXBuildFile", embed_bf, f"{{isa = PBXBuildFile; fileRef = {oid('product', 'RoomWidget')}; settings = {{ATTRIBUTES = (RemoveHeadersOnCopy, ); }}; }}")
        embed = oid("embed")
        add("PBXCopyFilesBuildPhase", embed, f"{{isa = PBXCopyFilesBuildPhase; buildActionMask = 2147483647; dstPath = \"\"; dstSubfolderSpec = 13; files = ({embed_bf}); name = \"Embed Foundation Extensions\"; runOnlyForDeploymentPostprocessing = 0; }}")
        phases.append(embed)
        proxy, dep = oid("proxy"), oid("dep")
        add("PBXContainerItemProxy", proxy, f"{{isa = PBXContainerItemProxy; containerPortal = {oid('project')}; proxyType = 1; remoteGlobalIDString = {oid('target', 'RoomWidget')}; remoteInfo = RoomWidget; }}")
        add("PBXTargetDependency", dep, f"{{isa = PBXTargetDependency; target = {oid('target', 'RoomWidget')}; targetProxy = {proxy}; }}")
        deps.append(dep)
    cl = cfg_list(t, {c: {**common, **per[t]} for c in ("Debug", "Release")})
    tid = oid("target", t)
    target_ids[t] = tid
    add("PBXNativeTarget", tid, f"{{isa = PBXNativeTarget; buildConfigurationList = {cl}; buildPhases = (" + ", ".join(phases) + "); buildRules = (); dependencies = (" + ", ".join(deps)
        + f"); name = {t}; productName = {t}; productReference = {oid('product', t)}; productType = {q(d['ptype'])}; }}")

pl = cfg_list("project", project_cfg)
add("PBXProject", oid("project"), f"{{isa = PBXProject; attributes = {{BuildIndependentTargetsInParallel = 1; LastSwiftUpdateCheck = 1540; LastUpgradeCheck = 1540; }}; buildConfigurationList = {pl}; "
    f"compatibilityVersion = \"Xcode 14.0\"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en, Base, ); mainGroup = {main_group}; "
    f"productRefGroup = {oid('group', 'Products')}; projectDirPath = \"\"; projectRoot = \"\"; targets = ({target_ids['RoomCoach']}, {target_ids['RoomWidget']}); }}")

out = ["// !$*UTF8*$!", "{", "\tarchiveVersion = 1;", "\tclasses = {", "\t};", "\tobjectVersion = 56;", "\tobjects = {"]
for section in sorted({s for s, _, _ in o}):
    out.append(f"\n/* Begin {section} section */")
    for s, i, body in sorted(x for x in o if x[0] == section):
        out.append(f"\t\t{i} = {body};")
    out.append(f"/* End {section} section */")
out += ["\t};", f"\trootObject = {oid('project')};", "}", ""]
proj = HERE / "RoomCoach.xcodeproj"
proj.mkdir(exist_ok=True)
(proj / "project.pbxproj").write_bytes("\n".join(out).encode())
print("wrote", proj / "project.pbxproj", {g: len(f) for g, f in groups.items()})
