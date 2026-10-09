# מקורות — מה תתי-הסוכנים מאזינים לו

(אושר 09/10/2026. להוספת מקור — שורה חדשה בטבלה, בלי לשנות קוד.)

## איך מחפשים בכל מקור
- **משתמשים בחיפוש ובסינון של האתר עצמו** (מילת חיפוש, ישראל, אזור) — לא מושכים את כל המשרות.
- מילות חיפוש מתוך [`search.md`](search.md): `Student`, `Intern`, `סטודנט` (ועוד אם יתברר שחסר).
- **רשת ביטחון:** פעם בשבוע סריקה מלאה בלי פילטר (קוד בלבד, לא משתמש ב-Pro) — כדי לתפוס משרות שהפילטר פספס (למשל "Early Career").
- הפילטרים של כל אתר נבחרים ע"י המוח **פעם אחת** (בהקמה או כשמשנים את `search.md`) ומוצגים למשתמש לאישור.

## אתרי חיפוש משרות — 3 סוכנים (סוכן לכל אתר)
| # | אתר | הערות |
|---|---|---|
| 1 | HireMeTech (juniors.hiremetech.com) | גם קבוצות הוואטסאפ מפנות לכאן |
| 2 | SecretHunter (secrethunter.io) | |
| 3 | Glassdoor | |

## חברות — 39 (סוכן לכל מערכת גיוס, 4-6 סוכנים)
מערכת הגיוס של כל חברה תזוהה בשלב 8 (בדיקת קריאה בלבד). העמודה "סוג" מסמנת חברות השמה/מיקור חוץ — מפרסמות משרות בשם חברות אחרות, נשמרות לבקשת המשתמש.

| # | חברה | משרות (מקור: פוסט, 10/2026) | סוג |
|---|---|---|---|
| 1 | Elbit Systems | 573 | |
| 2 | IAI - Israel Aerospace Industries | 516 | |
| 3 | Matrix | 476 | השמה / מיקור חוץ |
| 4 | NVIDIA | 409 | |
| 5 | Rafael Advanced Defense Systems | 363 | |
| 6 | Ness Technologies | 225 | השמה / מיקור חוץ |
| 7 | Check Point Software | 163 | |
| 8 | ONE Technologies | 156 | השמה / מיקור חוץ |
| 9 | Mobileye | 150 | |
| 10 | GAV Systems Group | 115 | השמה / מיקור חוץ |
| 11 | Apple | 104 | |
| 12 | Google | 103 | |
| 13 | Deloitte | 97 | |
| 14 | Palo Alto Networks | 94 | |
| 15 | KLA | 89 | |
| 16 | abra | 78 | השמה / מיקור חוץ |
| 17 | Applied Materials | 63 | |
| 18 | SolarEdge Technologies | 62 | |
| 19 | Amazon (כולל Annapurna Labs, 108) | 59 + 108 | אותו אתר משרות — amazon.jobs |
| 20 | ScaleOps | 53 | |
| 21 | CyberArk | 52 | |
| 22 | QualityAI | 52 | |
| 23 | Oracle | 49 | |
| 24 | Qualcomm | 45 | |
| 25 | DRS RADA Technologies | 45 | |
| 26 | Commit | 44 | השמה / מיקור חוץ |
| 27 | Nebius | 44 | |
| 28 | monday.com | 43 | |
| 29 | Aman Group | 42 | השמה / מיקור חוץ |
| 30 | G-STAT | 40 | השמה / מיקור חוץ |
| 31 | Experis | 40 | השמה / מיקור חוץ |
| 32 | Nova Ltd | 38 | |
| 33 | HiBob | 37 | |
| 34 | Wix | 36 | |
| 35 | Bynet Data Communications | 35 | השמה / מיקור חוץ |
| 36 | Microsoft | 35 | |
| 37 | DriveNets | 34 | |
| 38 | Cato Networks | 34 | |
| 39 | Teva Pharmaceuticals | 33 | |

## זיהוי מערכות הגיוס (שלב 8, צעד 1 — בתהליך, 10/10/2026)

| מערכת | חברות שאומתו | איך אומת / כתובת |
|---|---|---|
| Greenhouse | Nebius (42 בישראל), ScaleOps (32), Cato Networks (34) | `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs` — slugs: `nebius`, `scaleops`, `catonetworks` |
| Lever (EU) | Mobileye (160 בישראל) | `https://api.eu.lever.co/v0/postings/mobileye?mode=json` |
| Workday | NVIDIA, KLA, Applied Materials | POST `https://<host>/wday/cxs/<tenant>/<site>/jobs` עם `{"appliedFacets":{},"limit":20,"offset":0,"searchText":"..."}` — `nvidia.wd5.myworkdayjobs.com/nvidia/NVIDIAExternalCareerSite`, `kla.wd1.myworkdayjobs.com/kla/Search`, `amat.wd1.myworkdayjobs.com/amat/External` |
| Comeet | DriveNets, HiBob | מזהי משרה בפורמט Comeet (`BD.24D`, `E1.248`) בעמודי הקריירה. ה-API של Comeet דורש company uid + token מתוך עמוד הקריירה — לחלץ בשלב הבנייה |
| אתר עצמי | Check Point (`careers.checkpoint.com`), IAI (`jobs.iai.co.il`), Palo Alto (`jobs.paloaltonetworks.com`), Amazon (`amazon.jobs`), Google, Apple, Microsoft, Oracle | עמוד המשרות על דומיין של החברה |
| חוסם קריאה אוטומטית | Elbit (HTTP 403), Rafael (העמוד נבנה בדפדפן, מגיע ריק) | |
| עוד לא נבדקו | Matrix, Ness, ONE, GAV, Deloitte, abra, SolarEdge, CyberArk, QualityAI, Qualcomm, DRS RADA, Commit, monday.com, Aman, G-STAT, Experis, Nova, Wix, Bynet, Teva | |

⚠️ מלכודת: SmartRecruiters מחזיר HTTP 200 גם לחברה שלא קיימת (רשימה ריקה) — לבדוק `totalFound`, לא את קוד התשובה.

### הצעה (ממתינה לאישור המשתמש): שלוש שכבות
1. **מערכות ציבוריות** (Greenhouse, Lever, Workday, Comeet) — סוכן אחד לכל מערכת, קוד בלבד. נבנים ראשונים.
2. **חברות גדולות עם אתר עצמי** (Amazon, Google, Apple, Microsoft...) — מתאם נפרד לכל אחת. אחרי שכבה 1.
3. **חסומות / מסובכות** (Elbit, Rafael, IAI, כנראה גם חברות ההשמה) — בלי סוכן; המשרות שלהן מגיעות דרך סוכני אתרי החיפוש.

סה"כ ~4,500 משרות פתוחות — לכן הסינון באתר + "רק משרות חדשות" הם קריטיים.
