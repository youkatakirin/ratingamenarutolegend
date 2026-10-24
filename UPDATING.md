# Как внести новые игры (для Claude, по просьбе Prince)

Сайт: https://youkatakirin.github.io/ratingamenarutolegend/ (GitHub Pages, публикуется сам после push в main).
Копия: артефакт Claude https://claude.ai/artifact/9nVcEdBDzPofLtTuPCYSJJ. `netlify.toml` не трогать — его изменение запускает платную сборку на Netlify.
Плановой проверки нет: Prince сам пишет, когда проверить. Работай экономно — без лишних скриншотов и чтения больших файлов.

1. Данные: `python3 tools/season.py get index.html > season.json`. Последний записанный `msg` — граница новых сообщений.
2. Discord (встроенный браузер, пользователь там залогинен): канал результатов
   https://discord.com/channels/702273569304084642/1180907593493925958, правила
   https://discord.com/channels/702273569304084642/1453695056631300136. Сообщения — `li[id^="chat-messages-"]`,
   текст `[id^="message-content-"]`, время `<time datetime>` (UTC → UTC+5), картинки `a[href*="cdn.discordapp.com/attachments"]`.
   Прочитал — сразу закрой вкладку Discord (иначе у пользователя двойные уведомления).
3. Статистика: https://ac.narutolegend.dog/matches. Время там — конец матча по Москве ≈ время сообщения − 2 ч.
   `fetch('/match/ID')` + DOMParser, строки `tr`/`td`: ник, герой (первые 2 буквы — значок, отрезать), У/С/П, крипы, голд, урон, уровень.
   Матч засчитывается, только если совпали все 8 ников. Нет матча — героев/KDA/урон можно взять со скриншота, позже дополнить.
4. Скриншот итогов нужен для MVP/SVP (`award`, дают +5 с игры `points.awardFrom`), `tdmg` (урон по башням) и `taken` (полученный урон).
   Шелл не качает с Discord: открой картинку через media.discordapp.net, замени body на div с background-image (W×H картинки),
   добавь внизу метку `POS x,y`, двигай div и снимай `zoom` по тайлам (перед каждым — холостой zoom scale 0.1; проверяй метку).
   Если панель браузера скрыта (innerWidth = 0) — `resize_window` на нужный размер. Кадр скриншота бывает уменьшен относительно CSS
   (например 800×600 при 1024×768) — склеивай в том же масштабе. Сохрани `shots/game-N.jpg`.
5. Формат матча и правила очков — в README.md (бонусы серий, MVP/SVP и штрафы за баны сайт считает сам; в `d` только очки команды).
   Ники приводить к `roster`: Inneska→Inesska, YVNKXX→[YVN-KXX], letan_→letan, Panda_95→Panda95, Kimetsu_No→KimEtsu_No,
   Black_Reaper→black_reaper, Milancore→milancore, adsasd→Adsasd; на скриншоте Sutafokkusu = Frieren.
6. Запись: `python3 tools/season.py set index.html season.json`; карточки `python3 tools/make_card.py index.html N`
   (для артефакта ещё `--also <файл артефакта>` после `Artifact read`); commit + push; публикация артефакта с новыми shots/cards.
