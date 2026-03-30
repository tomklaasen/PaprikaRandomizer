$LOAD_PATH.unshift(File.dirname(__FILE__))

require 'nokogiri'
require 'recipe'

class Main
	BASE_DIR = File.join(File.dirname(__FILE__), "Paprika Export 2024-09-22 09.52.24 Alle recepten")


	def do_it
		# parse index.html
		doc = File.open(File.join(BASE_DIR, "index.html")) { |f| Nokogiri::HTML5(f) }

		# parse recipes
		recipes = []
		doc.xpath("//li").each do |line|
			recipe = Recipe.new
			recipe.title = line.text
			recipe.sourcefile = line.xpath("a/@href").text
			parse_recipe(recipe)
			recipes << recipe
		end

		hoofdgerechten = recipes.select {|r| r.categories.include?("Hoofdgerecht")}

		puts
		puts hoofdgerechten.sample.title
	end


	def parse_recipe(recipe)
		rdoc = File.open(File.join(BASE_DIR, recipe.sourcefile)) { |f| Nokogiri::HTML5(f) }
		categories_str = rdoc.xpath("//p[@itemprop='recipeCategory']").text
		categories = categories_str.split(",")
		categories.map! {|cat| cat.strip}
		recipe.categories = categories

		if categories.length == 0
			puts "No category found for #{recipe}"
		end
	end

end

Main.new.do_it
