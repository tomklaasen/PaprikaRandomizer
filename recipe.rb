class Recipe
	attr_accessor :title, :sourcefile, :categories

	def to_s
		"#{title} [#{sourcefile}] (categories: #{categories})"
	end
end

