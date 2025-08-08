# get .difyignore
cp ../microsoft_todo/.difyignore .

# replace author
# find author: .* and replace with "author: langgenius" in all yaml files
find . -type f -name "*.yaml" -exec sed -i 's/author: .*/author: langgenius/' {} \;

# fix version
yq eval '.meta.version = 0.0.1' -i manifest.yaml
yq eval '.version = 0.1.0' -i manifest.yaml

# echo dify_plugin>=0.4.3,<0.5.0 into requirements.txt
# remove original requirements.txt
rm requirements.txt
touch requirements.txt
echo "dify_plugin>=0.4.3,<0.5.0" > requirements.txt

# replace array
find . -type f -name "*.yaml" -exec sed -i 's/type: array.*/type: array/' {} \;
