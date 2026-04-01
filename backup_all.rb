#!/usr/bin/env ruby
# Sync all recipes from Paprika and render them as HTML.
# Suitable for running as a cronjob.
#
# Set HEALTHCHECKS_URL in .env to enable healthchecks.io monitoring.

require 'net/http'
require 'uri'
require_relative 'paprika'

def hc_ping(base_url, suffix = nil)
  return unless base_url
  url = suffix ? "#{base_url.chomp("/")}/#{suffix}" : base_url
  Net::HTTP.get(URI(url))
rescue => e
  $stderr.puts "  Warning: healthchecks.io ping failed: #{e}"
end

base_url = ENV["HEALTHCHECKS_URL"]

begin
  hc_ping(base_url, "start")

  paprika  = Paprika.new
  recipes  = paprika.sync_recipes

  total    = recipes.length
  rendered = 0

  recipes.each do |recipe|
    paprika.render_recipe_html(recipe)
    rendered += 1
    $stderr.print "\r  Rendering HTML: #{rendered}/#{total}" if $stderr.isatty
  end

  $stderr.puts "" if $stderr.isatty
  puts "Done. #{total} recipes synced, #{rendered} HTML pages rendered."

  hc_ping(base_url)
rescue => e
  $stderr.puts "Error: #{e}"
  hc_ping(base_url, "fail")
  exit 1
end
