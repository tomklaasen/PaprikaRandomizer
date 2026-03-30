require 'tmpdir'
require_relative 'paprika'

paprika  = Paprika.new
today    = Date.today
upcoming = paprika.meals
  .select  { |m| Date.parse(m["date"]) >= today }
  .sort_by { |m| [m["date"], m["order_flag"].to_i] }
  .group_by { |m| Date.parse(m["date"]) }

day_names = %w[zondag maandag dinsdag woensdag donderdag vrijdag zaterdag]

days_html = (today..today + 13).map do |date|
  meals_on_day = upcoming[date] || []
  is_today     = date == today

  meal_html = if meals_on_day.empty?
    "<span class=\"meal-name empty\">—</span>"
  else
    items = meals_on_day.map do |m|
      name = CGI.escapeHTML(m["name"])
      if m["recipe_uid"] && paprika.recipe_cached?(m["recipe_uid"])
        recipe    = paprika.load_recipe(m["recipe_uid"])
        html_path = paprika.render_recipe_html(recipe)
        "<span class=\"meal-name\"><a href=\"file://#{html_path}\">#{name}</a></span>"
      else
        "<span class=\"meal-name\">#{name}</span>"
      end
    end
    items.length == 1 ? items.first : "<div class=\"multi-meal\">#{items.join}</div>"
  end

  <<~HTML
    <div class="day#{is_today ? " today" : ""}">
      <div class="day-label">
        <div class="day-name">#{day_names[date.wday]}</div>
        <div class="day-date">#{date.strftime("%-d %B")}</div>
      </div>
      <div class="day-meals">#{meal_html}</div>
    </div>
  HTML
end.join

template = File.read(File.join(__dir__, "mealplan.html"))
html     = template.gsub("{{DAYS}}", days_html)

path = File.join(Dir.tmpdir, "paprika_plan.html")
File.write(path, html)
system("open", path)
