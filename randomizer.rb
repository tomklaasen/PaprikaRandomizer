require_relative 'paprika'

paprika = Paprika.new
recipes = paprika.sync_recipes

categories      = paprika.categories
hoofdgerecht_id = categories.find { |c| c["name"] == "Hoofdgerecht" }&.fetch("uid")
raise "Category 'Hoofdgerecht' not found" unless hoofdgerecht_id

hoofdgerechten = recipes.select { |r| r["categories"].include?(hoofdgerecht_id) }
paprika.open_recipe(hoofdgerechten.sample)
