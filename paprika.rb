require 'net/http'
require 'json'
require 'uri'
require 'fileutils'
require 'cgi'
require 'date'
require 'dotenv/load'

class Paprika
  API_BASE       = "https://www.paprikaapp.com/api/v1"
  THREADS        = 20
  CACHE_DIR      = File.join(__dir__, "cache")
  HTML_CACHE_DIR = File.join(__dir__, "html_cache")
  SKIP_HEADERS   = %w[BEREIDING INGREDIËNTEN INGREDIENTEN INSTRUCTIES].freeze

  def initialize
    @email    = ENV["PAPRIKA_EMAIL"]    or raise "PAPRIKA_EMAIL not set"
    @password = ENV["PAPRIKA_PASSWORD"] or raise "PAPRIKA_PASSWORD not set"
    FileUtils.mkdir_p(CACHE_DIR)
    FileUtils.mkdir_p(HTML_CACHE_DIR)
  end

  def sync_recipes
    listing = fetch_json("/sync/recipes/")["result"]
    stale   = listing.reject { |r| cache_valid?(r["uid"], r["hash"]) }
    unless stale.empty?
      $stderr.puts "Fetching #{stale.length} new/updated recipes (#{listing.length - stale.length} cached)..."
      fetch_in_parallel(stale.map { |r| r["uid"] })
    end
    listing.map { |r| load_cache(r["uid"]) }.reject { |r| r["in_trash"] }
  end

  def categories
    fetch_json("/sync/categories/")["result"]
  end

  def meals
    fetch_json("/sync/meals/")["result"]
  end

  def open_recipe(recipe)
    system("open", render_recipe_html(recipe))
  end

  def render_recipe_html(recipe)
    path = File.join(HTML_CACHE_DIR, "#{recipe["uid"]}.html")
    return path if File.exist?(path)

    template   = File.read(File.join(__dir__, "template.html"))
    first_word = recipe["name"].downcase.split.first.to_s

    ingredients = recipe["ingredients"].to_s.split("\n").reject(&:empty?).filter_map do |i|
      t = i.gsub(/&nbsp;/i, " ").strip
      next if SKIP_HEADERS.include?(t.upcase)
      "<li>#{CGI.escapeHTML(t)}</li>"
    end.join("\n          ")

    directions = recipe["directions"].to_s.split("\n").reject(&:empty?).filter_map do |d|
      t = d.gsub(/&nbsp;/i, " ").strip
      next if t =~ /\Aaantal personen/i
      next if t =~ /\A\s*\d+\s*minuten/i
      next if t =~ /\A\d+\z/
      if t == t.upcase && t =~ /[A-Z]/
        next if SKIP_HEADERS.include?(t)
        "<li class=\"section-header\">#{CGI.escapeHTML(t)}</li>"
      else
        next if first_word.length > 6 && t.downcase.start_with?(first_word)
        "<li><span>#{CGI.escapeHTML(t)}</span></li>"
      end
    end.join("\n          ")

    hero = recipe["image_url"].to_s.empty? ? "" :
      "<img class=\"hero\" src=\"#{CGI.escapeHTML(recipe["image_url"])}\" alt=\"#{CGI.escapeHTML(recipe["name"])}\">"

    meta_items = []
    meta_items << meta_item(icon_clock,  recipe["total_time"])                    unless recipe["total_time"].to_s.empty?
    meta_items << meta_item(icon_clock,  recipe["prep_time"] + " voorbereiding") unless recipe["prep_time"].to_s.empty?
    meta_items << meta_item(icon_clock,  recipe["cook_time"] + " kooktijd")      unless recipe["cook_time"].to_s.empty?
    meta_items << meta_item(icon_people, "#{recipe["servings"]} personen")        if recipe["servings"].to_i > 0
    unless recipe["source_url"].to_s.empty?
      label = CGI.escapeHTML(recipe["source"] || recipe["source_url"])
      meta_items << meta_item(icon_link, "<a href=\"#{CGI.escapeHTML(recipe["source_url"])}\">#{label}</a>")
    end
    meta = meta_items.empty? ? "" : "<div class=\"meta\">#{meta_items.join}</div>"

    description = recipe["description"].to_s.strip.empty? ? "" :
      "<p class=\"description\">#{CGI.escapeHTML(recipe["description"].strip)}</p>"

    html = template
      .gsub("{{TITLE}}",       CGI.escapeHTML(recipe["name"]))
      .gsub("{{HERO}}",        hero)
      .gsub("{{META}}",        meta)
      .gsub("{{DESCRIPTION}}", description)
      .gsub("{{INGREDIENTS}}", ingredients)
      .gsub("{{DIRECTIONS}}",  directions)

    File.write(path, html)
    path
  end

  def recipe_cached?(uid)
    cache_valid?(uid)
  end

  def load_recipe(uid)
    load_cache(uid)
  end

  private

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

  def cache_path(uid)
    File.join(CACHE_DIR, "#{uid}.json")
  end

  def cache_valid?(uid, hash = nil)
    path = cache_path(uid)
    return false unless File.exist?(path)
    hash.nil? || JSON.parse(File.read(path))["hash"] == hash
  end

  def load_cache(uid)
    JSON.parse(File.read(cache_path(uid)))
  end

  def fetch_json(path)
    uri = URI("#{API_BASE}#{path}")
    req = Net::HTTP::Get.new(uri)
    req.basic_auth(@email, @password)
    res = Net::HTTP.start(uri.host, uri.port, use_ssl: true) { |http| http.request(req) }
    JSON.parse(res.body)
  end

  def fetch_in_parallel(uids)
    queue = uids.dup
    mutex = Mutex.new

    THREADS.times.map do
      Thread.new do
        loop do
          uid = mutex.synchronize { queue.shift }
          break unless uid
          data = fetch_json("/sync/recipe/#{uid}/")["result"]
          File.write(cache_path(uid), JSON.generate(data))
        end
      end
    end.each(&:join)
  end
end
