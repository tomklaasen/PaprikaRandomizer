require 'tmpdir'
require_relative 'paprika'

paprika = Paprika.new

by_recipe = paprika.meals
  .select  { |m| m["recipe_uid"] }
  .sort_by { |m| m["date"] }
  .group_by { |m| m["recipe_uid"] }

entries = by_recipe
  .map do |uid, meals|
    { uid: uid, name: meals.first["name"], dates: meals.map { |m| Date.parse(m["date"]) } }
  end
  .sort_by { |e| [-e[:dates].length, e[:name].downcase] }

recipes_html = entries.map do |entry|
  name  = CGI.escapeHTML(entry[:name])
  count = entry[:dates].length
  dates = entry[:dates].sort.map { |d| d.strftime("%-d %B %Y") }.join(", ")

  name_html = if paprika.recipe_cached?(entry[:uid])
    recipe    = paprika.load_recipe(entry[:uid])
    html_path = paprika.render_recipe_html(recipe)
    label     = CGI.escapeHTML(recipe["name"].to_s.empty? ? entry[:name] : recipe["name"])
    "<a href=\"file://#{html_path}\">#{label}</a>"
  else
    name
  end

  <<~HTML
    <div class="recipe">
      <div class="count">#{count}</div>
      <div>
        <div class="recipe-name">#{name_html}</div>
        <div class="dates">#{CGI.escapeHTML(dates)}</div>
      </div>
    </div>
  HTML
end.join

template = File.read(File.join(__dir__, "history_template.html"))
html     = template.gsub("{{RECIPES}}", recipes_html)

path = File.join(Dir.tmpdir, "paprika_history.html")
File.write(path, html)
system("open", path)
