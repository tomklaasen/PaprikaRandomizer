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
                    .map { |i| "<li>#{CGI.escapeHTML(i)}</li>" }.join("\n          ")

    first_word = recipe["name"].downcase.split.first.to_s

    directions  = recipe["directions"].split("\n").reject(&:empty?).filter_map do |d|
      t = d.strip
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

    html = template
      .gsub("{{TITLE}}",       CGI.escapeHTML(recipe["name"]))
      .gsub("{{INGREDIENTS}}", ingredients)
      .gsub("{{DIRECTIONS}}",  directions)

    path = File.join(Dir.tmpdir, "paprika_recipe.html")
    File.write(path, html)
    system("open", path)
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
