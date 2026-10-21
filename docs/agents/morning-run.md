# הריצה של הבוקר — הוראות לסוכן הגדול

(גרסה 3, 21/10/2026. המשימה המתוזמנת של 09:05 מריצה את זה. הדרישות: [`orchestrator.md`](orchestrator.md), המוח: [`brain.md`](brain.md).)

## מי עושה מה
- **הקוד** רץ מ-Windows Task Scheduler (משימה "JobHunter morning", 08:00, הסקריפט `scripts/morning-task.cmd`), בלי Claude:
  `prepare` (תתי-סוכנים, סינון בקוד, תכנית) ← כותב `state/plan/next.json` ← `finish --wait` מחכה לסימן "סיימתי" של Claude ← דף ציבורי + גיבוי ל-git.
- **Claude (אתה)** — רק קריאת קבצים, כתיבה ללוח, והתראה. **אין שום פקודה להריץ.**

הריצה רצה **בלי אדם**. לכן:
- **לא מריצים פקודות** (לא Bash, לא PowerShell). לא כותבים ולא עורכים קבצים. קוראים בכלי Read בלבד.
- כלים: `ArtifactData` ו-`PushNotification` (ToolSearch: `select:ArtifactData,PushNotification`).
- הלוח: `https://claude.ai/artifact/BJhyULgtUPVBvZVUm313Fu`.
- משהו נכשל ← לא מחפשים דרך עוקפת. רושמים את השגיאה, ממשיכים בצעדים שלא תלויים בה, ומדווחים בסוף.

## הצעדים

**1. מה מוכן.** Read `C:\Users\kalma\IdeaProjects\JobHunter\state\plan\next.json`.
- הקובץ לא קיים, או ש-`date` בו **לא** התאריך של היום ← הקוד עוד לא רץ היום (המחשב נדלק מאוחר, או ש-Task Scheduler לא רץ). **לא עושים כלום מלבד:** `PushNotification`: `"JobHunter: הקוד של הבוקר עוד לא רץ — המשרות ייקלטו בריצה הבאה."` ומסיימים.
- אחרת: `D` = `date`. ב-`files` שלושה קבצים: `brain`, `batch`, `run`. ב-`errors` / `warnings` — מקורות שלא נקראו.

**2. תמונת מצב של הלוח.** `ArtifactData` `list` על `jobs`, `query.limit` 1000, `out_dir` = `C:\Users\kalma\IdeaProjects\JobHunter\state\board`. **לשמור את התוצאה** — יש בה ה-`version` של כל משרה.

**3. הכתיבות של הקוד.** Read `files.batch`. אם לא ריק — `ArtifactData` `batch` (עד 50 בכל קריאה): `op`, `collection`, `doc_id`, `file_path` (אם יש) כמו שהם, ו-`if_version` = ה-version של אותו `doc_id` מצעד 2. (`why` — רק להסבר, לא שולחים.) פריט `delete` (בלי `file_path`) = משרה שנסגרה לפני יותר משבוע — יוצאת מהלוח (החלטת המשתמש 21/10).

**4. המוח.** Read `files.brain`, [`brain.md`](brain.md), [`job-card.md`](../job-card.md), [`search.md`](../search.md). לכל פריט:
- **יש `borderline`** — אותה משרה כמו המועמד? רק אם התפקיד, הדרישות והמיקום תואמים ואין סתירה. בספק ← **לא כפילות**. כפילות ← לא יוצרים משרה; `update` למשרה הקיימת: `sightings` = הקיימות (מ-`state/board/jobs/<id>.json`) + `fields.sightings`, `alerts` = הקיימות + "אוחדה עם משרה דומה — בדוק". הסטטוס לא משתנה.
- **אחרת** — כרטיס לפי `brain.md` מ-`job` (הטקסט ב-`job.description`) ← מסמך חדש ב-`jobs`, `doc_id` = `doc_id` של הפריט: שדות הכרטיס + `fields` + `status` (`new` / `filtered`) + `history: [{status, at: "<D>T07:00:00Z", note: <history_note>}]`. בלי `if_version`.
- ב-`batch` של עד 50, `data` בתוך הקריאה.

**5. שורת הריצה.** `ArtifactData` `get` על `runs` / `D`. קיימת ← `set` עם `if_version` שלה; אחרת `set` בלי. `file_path` = `files.run`. אחר כך `update` (עם ה-version שחזר):
`{passed, brain_filtered, far, borderline: ["<משרה> — <מה הוחלט ולמה>"], summary: "<N> עברו · <M> סוננו ע\"י המוח · <P> סוננו בקוד · <K> כפילויות · <B> ממתינות"}`.

**6. תמונת מצב שנייה** — אותה קריאה של צעד 2 בדיוק (ממנה נבנה הדף הציבורי).

**7. סימן "סיימתי".** `ArtifactData` `get` על `runs` / `D` עם `out_dir` = `C:\Users\kalma\IdeaProjects\JobHunter\state\plan\done`. הקובץ שנוצר הוא הסימן ש-`finish` מחכה לו (דף ציבורי + גיבוי). **בלי הצעד הזה הבוקר לא נשמר** — לעשות אותו גם אם צעד קודם נכשל.

**8. התראה.** `PushNotification`: `"JobHunter: <N> משרות חדשות שמתאימות הבוקר. https://kalma57.github.io/JobHunter/"` + `" ⚠️ לא נקראו: <שמות>"` אם יש `errors`.

**דוח סיום** (עברית, קצר): נמצאו / סוננו בקוד / נקראו / עברו / כפילויות / מקרי גבול (ומה הוחלט) / שגיאות.

## אסור
- להריץ פקודה כלשהי, או לכתוב קובץ.
- לשנות סטטוס של משרה קיימת (רק המשתמש; "נסגרה" מגיע מהקוד בצעד 3).
- לקרוא את כל הלוח לתוך המוח — רק את `files.brain` ואת המשרות של מקרי הגבול.
- למחוק משרה מהלוח בעצמך. מחיקות מגיעות רק מהקוד, ב-`files.batch` (צעד 3).
