require 'net/http'
require 'json'
require 'uri'
require 'fileutils'
require 'tmpdir'
require 'cgi'
require 'dotenv/load'

class Main
  API_BASE     = "https://www.paprikaapp.com/api/v1"
  THREADS      = 20
  CACHE_DIR    = File.join(File.dirname(__FILE__), "cache")
  SKIP_HEADERS = %w[BEREIDING INGREDIËNTEN INGREDIENTEN].freeze

  def do_it
    email    = ENV["PAPRIKA_EMAIL"]    or raise "PAPRIKA_EMAIL not set"
    password = ENV["PAPRIKA_PASSWORD"] or raise "PAPRIKA_PASSWORD not set"

    FileUtils.mkdir_p(CACHE_DIR)

    categories      = fetch_json("/sync/categories/", email, password)["result"]
    hoofdgerecht_id = categories.find { |c| c["name"] == "Hoofdgerecht" }&.fetch("uid")
    raise "Category 'Hoofdgerecht' not found" unless hoofdgerecht_id

    listing = fetch_json("/sync/recipes/", email, password)["result"]
    stale   = listing.reject { |r| cache_valid?(r["uid"], r["hash"]) }

    unless stale.empty?
      $stderr.puts "Fetching #{stale.length} new/updated recipes (#{listing.length - stale.length} cached)..."
      fetch_in_parallel(stale.map { |r| r["uid"] }, email, password)
    end

    recipes = listing.map { |r| load_cache(r["uid"]) }
    hoofdgerechten = recipes.select { |r| r["categories"].include?(hoofdgerecht_id) }

    recipe = hoofdgerechten.sample
    open_in_browser(recipe)
  end

  def open_in_browser(recipe)
    template = File.read(File.join(File.dirname(__FILE__), "template.html"))

    ingredients = recipe["ingredients"].split("\n").reject(&:empty?)
                    .map { |i| "<li>#{CGI.escapeHTML(i.gsub(/&nbsp;/i, " ").strip)}</li>" }.join("\n          ")

    first_word = recipe["name"].downcase.split.first.to_s

    directions  = recipe["directions"].split("\n").reject(&:empty?).filter_map do |d|
      t = d.gsub(/&nbsp;/i, " ").strip
      next if t =~ /\Aaantal personen/i                        # servings metadata
      next if t =~ /\A\s*\d+\s*minuten/i                       # cook time metadata
      if t == t.upcase && t =~ /[A-Z]/                         # ALL CAPS line
        next if SKIP_HEADERS.include?(t)                       # generic section labels
        "<li class=\"section-header\">#{CGI.escapeHTML(t)}</li>"
      else
        next if first_word.length > 6 && t.downcase.start_with?(first_word)  # recipe title
        "<li><span>#{CGI.escapeHTML(t)}</span></li>"
      end
    end.join("\n          ")

    hero = recipe["image_url"].to_s.empty? ? "" :
      "<img class=\"hero\" src=\"#{CGI.escapeHTML(recipe["image_url"])}\" alt=\"#{CGI.escapeHTML(recipe["name"])}\">"

    meta_items = []
    meta_items << meta_item(icon_clock, recipe["total_time"])   unless recipe["total_time"].to_s.empty?
    meta_items << meta_item(icon_clock, recipe["prep_time"] + " voorbereiding") unless recipe["prep_time"].to_s.empty?
    meta_items << meta_item(icon_clock, recipe["cook_time"] + " kooktijd")      unless recipe["cook_time"].to_s.empty?
    meta_items << meta_item(icon_people, "#{recipe["servings"]} personen")      if recipe["servings"].to_i > 0
    unless recipe["source_url"].to_s.empty?
      label = CGI.escapeHTML(recipe["source"] || recipe["source_url"])
      meta_items << meta_item(icon_link, "<a href=\"#{CGI.escapeHTML(recipe["source_url"])}\">#{label}</a>")
    end
    meta = meta_items.empty? ? "" : "<div class=\"meta\">#{meta_items.join}</div>"

    html = template
      .gsub("{{TITLE}}",       CGI.escapeHTML(recipe["name"]))
      .gsub("{{HERO}}",        hero)
      .gsub("{{META}}",        meta)
      .gsub("{{INGREDIENTS}}", ingredients)
      .gsub("{{DIRECTIONS}}",  directions)

    path = File.join(Dir.tmpdir, "paprika_recipe.html")
    File.write(path, html)
    system("open", path)
  end

  def meta_item(icon, text)
    "<span class=\"meta-item\">#{icon}#{text}</span>"
  end

  def icon_clock
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
  end

  def icon_people
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>'
  end

  def icon_link
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>'
  end

  private

  def cache_path(uid)
    File.join(CACHE_DIR, "#{uid}.json")
  end

  def cache_valid?(uid, hash)
    path = cache_path(uid)
    return false unless File.exist?(path)
    JSON.parse(File.read(path))["hash"] == hash
  end

  def load_cache(uid)
    JSON.parse(File.read(cache_path(uid)))
  end

  def fetch_json(path, email, password)
    uri = URI("#{API_BASE}#{path}")
    req = Net::HTTP::Get.new(uri)
    req.basic_auth(email, password)
    res = Net::HTTP.start(uri.host, uri.port, use_ssl: true) { |http| http.request(req) }
    JSON.parse(res.body)
  end

  def fetch_in_parallel(uids, email, password)
    queue = uids.dup
    mutex = Mutex.new

    threads = THREADS.times.map do
      Thread.new do
        loop do
          uid = mutex.synchronize { queue.shift }
          break unless uid
          data = fetch_json("/sync/recipe/#{uid}/", email, password)["result"]
          File.write(cache_path(uid), JSON.generate(data))
        end
      end
    end

    threads.each(&:join)
  end
end

Main.new.do_it
