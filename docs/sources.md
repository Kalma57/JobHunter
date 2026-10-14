# מקורות — מה תתי-הסוכנים מאזינים לו

(אושר 09/10/2026. להוספת מקור — שורה חדשה בטבלה, בלי לשנות קוד.)

## איך מחפשים בכל מקור
- **משתמשים בחיפוש ובסינון של האתר עצמו** (מילת חיפוש, ישראל, אזור) — לא מושכים את כל המשרות.
- מילות חיפוש מתוך [`search.md`](search.md): `Student`, `Intern`, `סטודנט` (ועוד אם יתברר שחסר).
- **רשת ביטחון:** פעם בשבוע סריקה מלאה בלי פילטר (קוד בלבד, לא משתמש ב-Pro) — כדי לתפוס משרות שהפילטר פספס (למשל "Early Career").
- הפילטרים של כל אתר נבחרים ע"י המוח **פעם אחת** (בהקמה או כשמשנים את `search.md`) ומוצגים למשתמש לאישור.

## אתרי חיפוש משרות — סוכן לכל אתר
| # | אתר | מצב (שלב 9, עודכן 14/10/2026) |
|---|---|---|
| 4 | דרושים (drushim.co.il) | ✅ **פעיל** (14/10) — `drushim.py`. הממשק הציבורי שהאתר עצמו משתמש בו (`webapi.drushim.co.il/api/jobs/search`), מותר ב-robots.txt. חיפוש "סטודנט" / "סטודנטית" / "התמחות" בקטגוריות הייטק (5) והנדסה (10) — בלי קטגוריה המילה "סטודנט" מחזירה 950+ משרות, רובן אבטחה ומכירות. מילים באנגלית לא מחזירות כלום באתר. טקסט מלא ברשימה |
| 5 | JobMaster (jobmaster.co.il) | ✅ **פעיל** (14/10) — `jobmaster.py`. עמוד החיפוש הראשון (10 החדשות) לכל חיפוש; מעמוד 2 האתר מציג מסך התחברות — לא עוקפים, קוראים רק עמוד 1 כל בוקר. הטקסט המלא מעמוד המשרה (פעם אחת, במטמון) |
| — | LinkedIn, Indeed, AllJobs, Startup Nation Finder | ⛔ לא נקראים: LinkedIn ו-Indeed אוסרים קריאה אוטומטית (Indeed מחזיר 403), Startup Nation 403, ב-AllJobs התוצאות נטענות רק בדפדפן. חלופה: התראות במייל, כמו Glassdoor |
| 1 | HireMeTech (juniors.hiremetech.com) | ✅ **פעיל** — דפדפן ברקע (Playwright): הדפים מותרים ב-robots.txt, התוכן נטען מ-`/api/` שאסור לכלים אוטומטיים, אז לא קוראים לו ישירות — הדף טוען אותו כמו לכל מבקר. אחרי כמה דפי משרה האתר דורש התחברות "כדי לסנן בוטים" — לא עוקפים: ממשיכים עם פרטי הכרטיס מהרשימה (שם, תגיות, מיקום). שם החברה מוסתר למי שלא מחובר. גם קבוצות הוואטסאפ מפנות לכאן |
| 2 | SecretHunter (secrethunter.io) | ⛔ **חוסם** — שרת הנתונים מחזיר 403 גם לדפדפן אוטומטי. חלופה: התראות במייל (ממתין לתיבת מייל) |
| 3 | Glassdoor | ⛔ **חוסם** (403) ותנאי השימוש אוסרים קריאה אוטומטית. חלופה: התראות משרות במייל (ממתין לתיבת מייל) |

**כלל המשתמש (10/10/2026):** מאזינים לכל אתר שלא חוסם. אתר שחוסם — לא עוקפים (לא מתחזים, לא מתחברים אוטומטית).

## חברות — 50 (39 מהרשימה המקורית + 11 שנוספו ב-14/10; שלוש שכבות, ראה למטה)
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

## זיהוי מערכות הגיוס (שלב 8, צעד 1 — הושלם, 10/10/2026)

כל 39 החברות נבדקו (קריאה בלבד). השכבות **אושרו ע"י המשתמש** (10/10/2026).

### שכבה 1 — מערכות ציבוריות (סוכן אחד לכל מערכת, קוד בלבד, נבנים ראשונים)

| מערכת | חברות | איך קוראים |
|---|---|---|
| Greenhouse | Nebius (42 בישראל), ScaleOps (32), Cato Networks (34) | GET `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs` — slugs: `nebius`, `scaleops`, `catonetworks` |
| Lever (EU) | Mobileye (160 בישראל) | GET `https://api.eu.lever.co/v0/postings/mobileye?mode=json` |
| Workday | NVIDIA, KLA, Applied Materials | POST `https://<host>/wday/cxs/<tenant>/<site>/jobs` עם `{"appliedFacets":{},"limit":20,"offset":0,"searchText":"..."}` — `nvidia.wd5.myworkdayjobs.com/nvidia/NVIDIAExternalCareerSite`, `kla.wd1.myworkdayjobs.com/kla/Search`, `amat.wd1.myworkdayjobs.com/amat/External` |
| Eightfold (**חדש**) | Qualcomm (37 בישראל), Teva (35 בישראל) | Qualcomm: GET `https://careers.qualcomm.com/api/pcsx/search?domain=qualcomm.com&query=<מילה>&location=Israel&start=0`. Teva: GET `https://www.careers.teva/api/apply/v2/jobs?domain=tevapharm.com&location=Israel&start=0&num=10`. ⚠️ כל דומיין עונה רק לאחת משתי הכתובות (השנייה 403) |
| Comeet | DriveNets (35 בישראל), Nova (39) | GET `https://www.comeet.co/careers-api/2.0/company/<uid>/positions?token=<token>&details=true` — ה-uid וה-token הציבוריים מופיעים בעמוד Comeet של החברה (`comeet.com/jobs/<slug>/<uid>`, ב-`COMPANY_DATA`): DriveNets `72.006`, Nova `A5.007` |

### שכבה 2 — חברות עם אתר עצמי (✅ נבנתה 10/10/2026)

| חברה | איך נקרא | בישראל |
|---|---|---|
| Amazon (כולל Annapurna Labs) | `amazon.py` — `amazon.jobs/en/search.json?country=ISR` (טקסט מלא ברשימה) | 164 |
| Microsoft | Eightfold (`apply.careers.microsoft.com`, pcsx) — הגדרה בלבד; קצב איטי (`pause_seconds: 5`) בגלל 429 | 23 |
| Palo Alto Networks (**כולל CyberArk** — "Idira") | Workday (`paloaltonetworks.wd5`, `panwexternalcareers`) — הגדרה בלבד; אין אפשרות "Israel", נבחרים כל המשרדים בישראל | 142 |
| Wix | `smartrecruiters.py` — SmartRecruiters `Wix2` | 35 |
| Oracle | `oracle.py` — Oracle Recruiting Cloud REST (`eeho.fa.us2.oraclecloud.com`, `CX_45001`) | 32 |
| monday.com | `ashby.py` — Ashby `monday.com` | 42 |
| Deloitte | Comeet (`F7.00B`) — הגדרה בלבד | 67 |
| Apple | `apple.py` — הנתונים בתוך העמוד; חיפוש של האתר לכל מילת חיפוש | 101 |
| Google | `google.py` — הנתונים (כולל טקסט מלא) בתוך עמוד התוצאות; חיפוש לכל מילת חיפוש | 90 |
| HiBob | `hibob.py` — עמוד הקריירה הציבורי בלבד (שם, מחלקה, סוג, מיקום); הטקסט המלא דורש התחברות | 19 |

### נוספו 14/10/2026 — 11 חברות, הגדרה בלבד (מערכות קיימות)

| חברה | מערכת | בישראל (14/10) |
|---|---|---|
| Intel (כולל קריית גת) | Workday `intel.wd1` / `External` | 21 |
| Marvell | Workday `marvell.wd1` / `MarvellCareers` | 11 (9 משרות Intern) |
| HP (Indigo) | Workday `hp.wd5` / `ExternalCareerSite` | 11 |
| Salesforce | Workday `salesforce.wd12` / `External_Career_Site` | 14 |
| Cisco | Workday `cisco.wd5` / `Cisco_Careers` | 37 |
| Wiz | Greenhouse `wizinc` | 23 |
| JFrog | Greenhouse `jfrog` | 21 |
| Taboola | Greenhouse `taboola` | 22 |
| Similarweb | Greenhouse `similarweb` | 28 |
| Payoneer | Greenhouse `payoneer` | 24 |
| SentinelOne | Greenhouse `sentinellabs` | 18 |

נבדקו ולא נוספו: eBay (אין אפשרות "Israel" בפילטר), Amdocs (Eightfold מחזיר משרה אחת בישראל), NICE / Dell / Intuit / IBM / Western Digital (כתובת Workday לא נמצאה), Fiverr (Comeet — דרוש token, אפשר להוסיף בהמשך).

### שכבה 3 — בלי סוכן משלהן (המשרות מגיעות דרך סוכני אתרי החיפוש, שלב 9)

| חברה | סיבה |
|---|---|
| Elbit | HTTP 403 |
| Rafael | העמוד נבנה בדפדפן ומגיע ריק |
| IAI | אתר עצמי מסובך (`jobs.iai.co.il`) |
| DRS RADA | HTTP 403 (גם `leonardodrs.com`) |
| ONE Technologies | HTTP 403 |
| SolarEdge | האתר מחזיר 403, וה-uid שלה ב-Comeet לא נמצא בשום מקום ציבורי |
| Check Point | HTTP 403 |
| QualityAI | תעודת האבטחה של אתר המשרות פגה — לא מבטלים בדיקת אבטחה. ממילא חברת QA (מחוץ לחיפוש) |
| חברות השמה: Matrix (`matrix.co.il/jobs`), Ness (`ness-tech.co.il/careers`), GAV (`gav.co.il/jobs`), abra (`abra-it.com/career`), Commit (`commit.co.il`), Aman (`aman.co.il/careers`), G-STAT (`g-stat.com/careers`), Experis (`experis.co.il/search`), Bynet (`bynet.co.il/career`) | אתרי WordPress / עצמיים, כל אחד במבנה אחר; מפרסמות בשם חברות אחרות — וממילא מופיעות באתרי החיפוש. אם יתברר בשבוע הצל שמפספסים מהן משרות — נוסיף מתאם |

⚠️ מלכודות: SmartRecruiters מחזיר HTTP 200 גם לחברה שלא קיימת (רשימה ריקה) — לבדוק `totalFound`. גם Workable מחזיר 200 עם רשימה ריקה לכל שם — לא סימן לקיום.

סה"כ ~4,500 משרות פתוחות — לכן הסינון באתר + "רק משרות חדשות" הם קריטיים.
