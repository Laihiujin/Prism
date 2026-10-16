# Door, lock and person: physical and interaction logic

Category rules for any scene with an entrance door and a smart lock (智能门锁). Brand-neutral; brand adapters add model specifics. Use it to build the product logic sheet ([product research](product-research.md)) and to review every generated or replaced scene. Evidence levels: **[std]** standard or manufacturer spec, **[cat]** consistent across several manufacturers' manuals or product pages, **[inf]** inferred from geometry; confirm per model before stating it as fact.

## 1. Door anatomy

| Part | Where it is | Visible when |
| --- | --- | --- |
| Leaf (门扇) | The moving slab | Always |
| Frame (门框) | Fixed around the leaf, set in the wall | Always |
| Hinge edge (合页侧) | One vertical edge of the leaf; 3 hinges up to about 2.1 m leaf height, 4 above [cat] | Hinge barrels show on the face toward which the door swings |
| Lock edge (锁侧) | The opposite vertical edge | Lock panels sit on both faces near this edge |
| Mortise faceplate, latch and deadbolts (锁体导向片, 斜舌, 方舌) | On the lock edge of the leaf; the strike plate is on the frame | Only when the door is open or seen edge-on |
| Top/bottom rods (天地钩) | Top and bottom edges of the leaf, on some security doors | Only when open |

- Typical Chinese entrance-door leaf: 860 or 960 mm wide, 1970 or 2050 mm high; gaps between leaf and frame about 2–3 mm at the sides and top [cat].
- Smart-lock door thickness range: 38–120 mm for most push-pull models; wooden and steel security doors (防盗门) [cat].
- Handing is named standing **outside**: 左开/右开 by hinge side, 内开/外开 by swing direction (four combinations) [cat]. One image must be consistent: hinge side, swing direction, lock side and handle orientation all agree.
- Peephole height is commonly about 1.5–1.6 m [cat, non-normative]. Lock-panel heights follow each model's drilling template [std per model]; do not invent a number.

## 2. How a smart lock is built

- Two panels on opposite faces of the same leaf, at the same height, connected through the leaf by a spindle (方杆/方钢) and cables, driving one mortise lock body (锁体) inside the leaf [cat].
- **Exterior panel (前面板, outside face):** camera/peephole and face module (usually at the top), keypad and doorbell, fingerprint sensor, card area, emergency power port and mechanical key cylinder (often hidden under a cover or on the bottom end).
- **Interior panel (后面板, inside face):** indoor screen (if any), handle or grip with hand sensor, deadlock knob (反锁旋钮), battery compartment and charging port.
- Panels are long and narrow: about 400–450 mm long and 70–90 mm wide on current push-pull models [cat], i.e. roughly a forearm plus hand, about a fifth of the door height.
- The exterior panel faces the corridor or outdoors and carries the weather rating; the battery and charging port are on the interior panel [cat].

## 3. Two families, two interactions

### Push-pull (推拉式)

1. Approach; radar or touch wakes the lock.
2. Verify: face (person upright, facing the top camera, about 0.3–1 m away), fingerprint, code, card, phone or watch.
3. Fully automatic bodies retract the bolts by themselves; the user then **pushes or pulls the panel body itself**, which is the grip. Fingers hook behind the exterior panel, which is why many models put the fingerprint sensor on its back or underside ("一勾一拉") [cat].
4. Inward-opening door: push from outside, pull from inside. Outward-opening: pull from outside, push from inside [inf from geometry].
5. Inside: grip the interior handle; a hand sensor or button releases the lock, then push or pull [cat]. Closing the door auto-locks.
6. Pinch risk is higher on inward-opening doors; manuals advise using the hand on the hinge side (左开门用左手) [cat].

### Lever handle (把手式)

- Horizontal lever at rest, pivot near the lock edge, free end pointing toward the hinge side [cat]. Pressing the lever down retracts the latch (semi-automatic). The fingerprint sensor is often on the lever.
- The lever is never vertical at rest, never pointing past the door edge, and the outside and inside levers mirror each other through the leaf.

### Common to both

- Deadlock knob turned from inside blocks every outside method, including the key [cat].
- Emergency: power bank into the exterior Type-C, or the hidden mechanical key [cat].
- Doorbell on the exterior panel lights the indoor screen; the indoor screen and phone show the **outside** camera view.

## 4. Camera and screen logic

- The peephole camera looks outward from the exterior panel at visitor height. Its picture is a wide-angle view of the corridor or porch: visitor facing the door, slight fisheye, sometimes infrared monochrome at night [cat].
- Dual-camera models differ: some add a floor-facing camera at the bottom end (parcels, children), others a second wide or zoom lens at the top. Check the model sheet.
- An indoor screen never shows the inside of the home, the user's own face from inside, or anything the exterior camera could not see.

## 5. Person and lock

- Reach: keypad and fingerprint at roughly waist-to-chest height, camera at chest-to-shoulder height; face unlock covers users about 1.2–2 m tall [cat].
- The person stands on the same side as the panel they use, facing the door. Face unlock means looking at the camera within arm's length, hands free (bags, child, parcels are typical motivations).
- Children and elderly users: face, card or watch rather than keypad; the interior screen is used to check visitors before opening.
- A courier or visitor waits outside and faces the exterior camera; they never touch the interior panel.

## 5a. Patterns across brands (competitor survey)

Read across the main Chinese smart-lock brands (Dessmann, Xiaomi, Huawei, Lockin, VOC, Ezviz, TCL and others) on 2026-10-17. Use these to choose a believable gesture for the sensor the model actually has; never show a gesture for a sensor the model lacks.

| Unlock method | What the person physically does | Where the sensor is | Seen on |
| --- | --- | --- | --- |
| 3D face | Stands upright 0.3–1 m away, faces the top of the exterior panel, hands free | Top of exterior panel, next to the peephole camera | Most mid/high models |
| Palm vein (掌静脉) | Holds an open palm flat toward the panel, about 10–30 cm away, fingers slightly spread, no touch | A dark sensor window on the exterior panel face | Dessmann Q50FV, Xiaomi M30 Pro, Huawei 2 Pro |
| Finger vein (指静脉) | Rests one finger on or in a groove/ring sensor | Dedicated finger slot on the exterior panel | Lockin, VOC |
| Hidden fingerprint (隐藏指纹) | Fingertip lands on the sensor while the fingers hook behind the panel to pull | Back or underside of the exterior panel | Push-pull models at several brands |
| Front fingerprint | Presses a fingertip on a visible pad | Front of the panel or top of the lever | Lever and older models |
| Keypad / card / phone / watch | Taps code; holds card or watch to the card area; phone app remotely | Keypad on the exterior panel face | All |

- **Wake-up:** radar or body sensing wakes the lock as a person approaches ("人到门开"); in scenes the panel lights up as someone arrives, not after they touch it.
- **Night and backlight:** infrared fill light gives a monochrome image; on metal security doors the IR reflects, often over-exposing the lower face. Night camera views should look IR-grey, not full colour, unless the model claims colour night vision.
- **Camera layouts differ by brand and model:** single wide peephole (around 144–165° at several brands), panorama plus face close-up both at the top, or top plus floor-facing bottom camera. Match the model.
- **Indoor screens:** 4–5 inch portrait screens on the interior panel are the norm; a visitor rings, the screen wakes with the outside view. Some brands add a detachable or second small screen.
- **Smart-home tie-ins:** opening can trigger lights or scenes (Xiaomi, Huawei ecosystems); an entry-hall light switching on as the door opens is believable, but only show ecosystem effects the brand supports.
- **Operating with full hands:** face and palm vein are the methods that work while carrying bags or a child; keypad and fingerprint need a free hand. Elderly and children are usually shown with face, card or watch.

## 6. Checkable rules for any scene

1. The lock is on the leaf near the lock edge, never on the hinge edge, the frame or the wall.
2. A closed door shows at most one panel per view. Both panels together only in an edge-on open door, a divided split frame or an obvious packshot.
3. Hinges, swing direction, lock side and lever direction are consistent with one handing.
4. Exterior-panel scenes have a corridor, porch or outdoor background; interior-panel scenes have a home interior.
5. Panel scale is about a fifth of the door height and narrower than the door stile; it sits vertically and flush, not floating.
6. Mortise faceplate, bolts and rods appear only on an open door's edge; on a closed door they are hidden.
7. Push-pull: the hand grips the panel body or interior handle and pushes or pulls along the swing. Lever: the hand presses down.
8. Person, panel and camera are on the same side; face unlock within about 1 m, facing the camera.
9. Screen content is the outside view.
10. Keypad digits, logos and text read correctly (not mirrored), and the button layout matches the source images.
11. The unlock gesture matches a sensor the model really has (no palm held up to a lock without palm vein, no fingertip on a front pad when the sensor is hidden underneath).

## 7. Frequent failures in generated images

- Lock on the hinge side, or hinge barrels on both sides of a door.
- Exterior and interior panels side by side on one face.
- Lever pointing up or toward the door edge; push-pull grip shown as a lever.
- Camera pointing into the room; indoor screen showing an indoor scene.
- Panel floating in front of the door, mounted on the wall, or scaled like a phone or like a column.
- Bolts sticking out of a closed door; mortise faceplate on the door face.
- Person unlocking from the wrong side, reaching across the door, or looking away during face unlock.
- Opening direction contradicts the hinges or the handle being pulled.

## 8. Research method for a new model

Search with **brand + model** together; model names collide across brands (the same series name can belong to two different lock makers). Prefer the brand's own detail page and its 基本参数 table, then the installation template, then retailer listings; treat buying guides as hints only. Record which panel owns each part, the handle family, camera layout, sizes, colours and door range in the product sheet before generating.

## Sources (checked 2026-10-17)

- Lock body, spindle, faceplate, top/bottom rods: [Sohu: 智能锁锁体结构基本解析](https://www.sohu.com/a/510076376_121005973), [知乎: 智能门锁锁体的内外基础结构剖析](https://zhuanlan.zhihu.com/p/361503997).
- Push-pull operation, inside release, deadlock and emergency opening: [Philips Alpha push-pull manual](https://www.documents.philips.com/assets/20230823/83e5f3f46024468e9e0bb067005a2839.pdf), [Huawei indoor unlocking](https://consumer.huawei.com/cn/support/content/zh-cn15879834/).
- Pinch risk on inward-opening doors: [什么值得买: 推拉锁夹手](https://post.smzdm.com/p/axldpovd/), [知乎问答](https://www.zhihu.com/question/485371529).
- Installation geometry: [Philips DDL801 manual](https://www.documents.philips.com/assets/20241230/5e7daa1319c64137b8d7b25600230a0f.pdf), [Kirz PP9000 manual](https://htdocs.kirz.com/HTHMKT/manual/ddl/PP9000-installation-en.pdf), [Lerond: thickness and backset](https://www.lerond.tech/smart-lock-door-thickness-backset-compatibility/).
- Door sizes, hinges, gaps, peephole height: [Sohu: 门的标准尺寸](https://www.sohu.com/a/942625875_420289), [设计本: 防盗门宽度](https://m.shejiben.com/ask/wenda/447963.html).
- Handing from outside and four combinations: [新浪: 智能门锁安装教程](https://k.sina.cn/article_7879923745_1d5ae182106801bza4.html).
- Cross-brand biometrics, palm-vein distance, hidden fingerprint, camera angles: [知乎: 掌静脉锁测评](https://zhuanlan.zhihu.com/p/692991816), [什么值得买: 德施曼人脸掌静脉](https://post.smzdm.com/p/awdr9gpm/), [知乎: 四大品牌对比](https://zhuanlan.zhihu.com/p/555405494), [对比窝: 德施曼 R7/Q50](https://www.vsbuys.com/206219.html).
- Face unlock at night, backlight and IR reflection on metal doors: [CSDN: 人脸猫眼弱光实测](https://aiot.csdn.net/6a0ff51410ee7a33f2745cae.html), [知乎: 人脸识别智能锁实测](https://zhuanlan.zhihu.com/p/703205465), [什么值得买: 小米人脸锁体验](https://post.smzdm.com/p/a5ovrpx3/).
- Panel sizes, face range, door range, finger-hook interaction, lever vs push-pull: official product pages and parameter tables of current push-pull and lever models from a major Chinese smart-lock maker (model details kept in the private brand adapter).
