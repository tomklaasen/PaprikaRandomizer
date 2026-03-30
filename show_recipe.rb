require_relative 'paprika'

uid = ARGV[0] or abort "Usage: ruby show_recipe.rb <uid>"

paprika = Paprika.new
paprika.sync_recipes
paprika.open_recipe(paprika.load_recipe(uid))
