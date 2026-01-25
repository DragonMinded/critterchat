const config = {
    verbose: true,
    testMatch: ["**/test/**/*.js"],
    preset: 'ts-jest',
    transform: {
        '^.+\\.(js|jsx)$': 'babel-jest',
      }
};

module.exports = config;
