# הריצה של הבוקר — הוראות לסוכן הגדול

(גרסה 2, 14/10/2026. זו ההוראה שהמשימה המתוזמנת של 09:05 מריצה. הדרישות: [`orchestrator.md`](orchestrator.md), המוח: [`brain.md`](brain.md).)

הריצה רצה **בלי אדם**. לכן:
- **פקודות מריצים רק בכלי Bash, ורק את שתי הפקודות שכתובות כאן, בדיוק כפי שהן.** בלי `cd`, בלי פקודות נוספות, בלי PowerShell. כל פקודה אחרת תעצור את הריצה ותחכה לאישור.
- קבצים קוראים בכלי Read. **לא כותבים קבצים** — כל הכתיבות הולכות ללוח דרך `ArtifactData`.
- הלוח: `https://claude.ai/artifact/BJhyULgtUPVBvZVUm313Fu`. הכלים `ArtifactData` ו-`PushNotification` נטענים עם ToolSearch: `select:ArtifactData,PushNotification`.
- משהו נכשל ← לא מחפשים דרך עוקפת. רושמים את השגיאה המדויקת, ממשיכים בצעדים שלא תלויים בה, ומדווחים בסוף.

## הצעדים

**1. תמונת מצב של הלוח.** `ArtifactData` `list` על `jobs`, `query.limit` 1000, `out_dir` = `C:\Users\kalma\IdeaProjects\JobHunter\state\board`. **לשמור את התוצאה** — יש בה ה-`version` של כל משרה, וצריך אותו לכל עדכון.

**2. הכנה בקוד (פקודה אחת).**
```
.venv/Scripts/python.exe -m jobhunter.morning prepare
```
הפקודה מריצה את כל תתי-הסוכנים (ביום ראשון — הסריקה השבועית), מסננת בקוד את מה שבטוח לא מתאים (`config/prefilter.json`), מורידה כפילויות ודאיות, ומכינה קבצים. הפלט קצר: מספרים, שגיאות, ושלושה קבצים:
- `files.brain` — המשרות שהמוח צריך לקרוא (עד 40).
- `files.batch` — כתיבות שהקוד כבר הכין (מקור נוסף למשרה קיימת, "נסגרה", כלל 30 הימים).
- `files.run` — שורת הריצה.

**3. הכתיבות של הקוד.** קוראים את `files.batch`. אם הרשימה לא ריקה — `ArtifactData` `batch` עם כל הפריטים (עד 50 בכל קריאה): `op`, `collection`, `doc_id`, `file_path` כמו שהם, ו-`if_version` = ה-version של אותו `doc_id` מהתוצאה של צעד 1. (השדה `why` רק להסבר — לא שולחים אותו.)

**4. המוח.** קוראים את `files.brain`, את [`brain.md`](brain.md), [`job-card.md`](../job-card.md) ו-[`search.md`](../search.md). לכל פריט:
- **אם יש `borderline`** — להחליט אם זו אותה משרה כמו המועמד: רק אם התפקיד, הדרישות והמיקום תואמים ואין סתירה. בספק ← **לא כפילות**. אם כפילות ← לא יוצרים משרה; `update` למשרה הקיימת: `sightings` = הרשימה הקיימת (מקובץ `state/board/jobs/<id>.json`) ועוד הפריטים מ-`fields.sightings`, ו-`alerts` = הקיימות ועוד "אוחדה עם משרה דומה — בדוק". הסטטוס לא משתנה.
- **אחרת** — כרטיס לפי `brain.md` מתוך `job` (הטקסט המלא ב-`job.description`), ואז מסמך חדש ב-`jobs`, `doc_id` = `doc_id` של הפריט: כל שדות הכרטיס + כל מה שב-`fields` + `status` (`new` / `filtered`) + `history: [{status, at: "<D>T07:00:00Z", note: <history_note>}]`. בלי `if_version` (מסמך חדש).
- כותבים ב-`batch` של עד 50, `data` בתוך הקריאה.

**5. שורת הריצה.** `ArtifactData` `get` על `runs` / `<D>` (D = `date` מצעד 2). אם קיימת — `set` עם `if_version` שלה; אחרת `set` בלי. `file_path` = `files.run`. אחר כך `update` לאותו מסמך (עם ה-version שחזר) עם:
`{passed: <כמה עברו>, brain_filtered: <כמה סוננו ע"י המוח>, far: <כמה רחוקות>, borderline: ["<משרה> — <מה הוחלט ולמה>"...], summary: "<N> עברו · <M> סוננו ע\"י המוח · <P> סוננו בקוד · <K> כפילויות · <B> ממתינות"}`.

**6. תמונת מצב שנייה + סיום (פקודה שנייה).** שוב צעד 1 (אותה קריאה בדיוק), ואז:
```
.venv/Scripts/python.exe -m jobhunter.morning finish
```
בונה את הדף הציבורי (`public/index.html`) מהלוח המעודכן ודוחף אותו ל-GitHub Pages, ושומר גיבוי של `state/seen` ו-`state/inbox` ב-git (commit + push). מהפלט לוקחים `git`, `public.published` ו-`public_error` אם יש.

**7. התראה.** `PushNotification`: `"JobHunter: <N> משרות חדשות שמתאימות הבוקר. הלוח: https://claude.ai/artifact/BJhyULgtUPVBvZVUm313Fu"`. אם יש שגיאות מצעד 2 — להוסיף `" ⚠️ לא נקראו: <שמות>"`; אם `git` לא `ok` — `" ⚠️ הגיבוי נכשל"`.

**דוח סיום** (עברית, קצר): כמה נמצאו / סוננו בקוד / נקראו / עברו / כפילויות / מקרי גבול (ומה הוחלט) / שגיאות.

## אסור
- לשנות סטטוס של משרה קיימת (רק המשתמש משנה סטטוס; "נסגרה" מגיע מהקוד בצעד 3).
- לקרוא את כל הלוח לתוך המוח — רק את `files.brain` ואת המשרות הספציפיות של מקרי הגבול.
- למחוק משרה מהלוח.
- להריץ פקודה שלא כתובה כאן.
